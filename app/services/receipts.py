"""Generate an inclusion receipt only from a consistent persisted batch."""

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BatchEntry, MerkleBatch, Registration
from app.schemas.receipts import InclusionProof, ProtectedRegistration, Receipt, ReceiptBatch
from integrity.commitments import encode_registration
from integrity.merkle import merkle_root
from integrity.proofs import inclusion_proof


class UnsealedRegistration(ValueError):
    """A pending registration cannot receive an inclusion receipt."""


class ReceiptIntegrityError(ValueError):
    """Stored evidence must be consistent before a receipt is issued."""


def build_receipt(session: Session, registration_id: UUID) -> Receipt | None:
    record = session.get(Registration, registration_id)
    if record is None:
        return None
    entry = session.scalar(select(BatchEntry).where(BatchEntry.registration_id == registration_id))
    if entry is None:
        raise UnsealedRegistration("Registration is not in a sealed batch")
    batch = session.get(MerkleBatch, entry.batch_id)
    if batch is None or not 1 <= batch.tree_size <= 1000:
        raise ReceiptIntegrityError("Invalid batch")
    members = list(session.scalars(
        select(BatchEntry).where(BatchEntry.batch_id == batch.id)
        .order_by(BatchEntry.position).limit(1001)
    ))
    if len(members) != batch.tree_size or [member.position for member in members] != list(range(batch.tree_size)):
        raise ReceiptIntegrityError("Incomplete batch")
    if not 0 <= entry.position < batch.tree_size or members[entry.position].registration_id != record.id:
        raise ReceiptIntegrityError("Invalid batch position")
    encoded = encode_registration(
        registration_id=record.id, digest=record.digest,
        received_at=record.received_at, registration_metadata=record.registration_metadata,
        hash_algorithm=record.hash_algorithm, format_version=record.format_version,
    )
    if encoded != entry.entry_bytes:
        raise ReceiptIntegrityError("Registration does not match its sealed snapshot")
    snapshots = [member.entry_bytes for member in members]
    if merkle_root(snapshots, version=batch.merkle_version).hex() != batch.root:
        raise ReceiptIntegrityError("Stored batch root does not match its entries")
    return Receipt(
        registration=ProtectedRegistration.model_validate(json.loads(encoded)),
        batch=ReceiptBatch(
            id=batch.id, root=batch.root, tree_size=batch.tree_size,
            merkle_version=batch.merkle_version, sealed_at=batch.sealed_at,
        ),
        inclusion_proof=InclusionProof(
            leaf_index=entry.position,
            audit_path=[node.hex() for node in inclusion_proof(snapshots, entry.position, version=batch.merkle_version)],
        ),
    )
