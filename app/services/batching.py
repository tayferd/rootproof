"""Seal a bounded set of registrations atomically; do not publish witness claims."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, select, text
from sqlalchemy.orm import Session

from app.db.models import BatchEntry, MerkleBatch, Registration
from integrity.commitments import encode_registration
from integrity.merkle import MERKLE_VERSION, merkle_root


@dataclass(frozen=True)
class SealedBatch:
    id: UUID
    root: str
    tree_size: int
    merkle_version: str
    sealed_at: datetime


def seal_batch(session: Session, *, limit: int = 1000) -> SealedBatch | None:
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Batch limit must be between 1 and 1000")
    with session.begin():
        # Serialize sealers in PostgreSQL; the lock is released on commit/rollback.
        session.execute(text("SELECT pg_advisory_xact_lock(721004021)"))
        pending = list(session.scalars(
            select(Registration)
            .where(~exists().where(BatchEntry.registration_id == Registration.id))
            .order_by(Registration.received_at, Registration.id)
            .limit(limit)
            .with_for_update()
        ))
        if not pending:
            return None
        entries = [encode_registration(
            registration_id=record.id, digest=record.digest,
            received_at=record.received_at, registration_metadata=record.registration_metadata,
            hash_algorithm=record.hash_algorithm, format_version=record.format_version,
        ) for record in pending]
        batch = MerkleBatch(root=merkle_root(entries).hex(), tree_size=len(entries), merkle_version=MERKLE_VERSION)
        session.add(batch)
        session.flush()
        session.refresh(batch)
        session.add_all(BatchEntry(
            batch_id=batch.id, position=index, registration_id=record.id, entry_bytes=entry,
        ) for index, (record, entry) in enumerate(zip(pending, entries, strict=True)))
        session.flush()
        result = SealedBatch(batch.id, batch.root, batch.tree_size, batch.merkle_version, batch.sealed_at)
    return result
