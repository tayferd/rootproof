"""Receipt export, privacy, pending states, and refusal of inconsistent evidence."""

from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.registrations import get_session
from app.db.models import MerkleBatch, Registration
from app.services.batching import seal_batch
from app.services.receipts import build_receipt
from integrity.commitments import encode_registration


def sealed_registrations(client, connection, count):
    results = [client.post("/registrations", json={
        "digest": f"{i:064x}", "registration_metadata": {"name": f"private-document-{i}"},
    }).json() for i in range(count)]
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        seal_batch(session)
    return results


@pytest.mark.parametrize("count", [1, 2, 3, 5])
def test_receipt_contains_only_target_metadata_and_valid_path(database_client, count) -> None:
    client, connection = database_client
    registrations = sealed_registrations(client, connection, count)
    # A separate recursive proof check avoids relying on the production builder.
    for registration in registrations:
        response = client.get(f'/registrations/{registration["id"]}/receipt')
        assert response.status_code == 200
        receipt = response.json()
        assert receipt["status"] == "sealed_pending_witnesses"
        assert receipt["receipt_version"] == "rootproof.receipt.v1"
        assert receipt["batch"]["tree_size"] == count
        assert response.headers["Content-Disposition"] == f'attachment; filename="rootproof-{registration["id"]}.json"'
        assert response.headers["Cache-Control"] == "no-store"
        protected = receipt["registration"]
        assert protected["id"] == registration["id"]
        for other in registrations:
            if other["id"] != registration["id"]:
                assert other["registration_metadata"]["name"] not in response.text

        encoded = encode_registration(
            registration_id=UUID(protected["id"]), digest=protected["digest"],
            received_at=datetime.fromisoformat(protected["received_at"]),
            registration_metadata=protected["registration_metadata"],
        )
        path = iter(bytes.fromhex(node) for node in receipt["inclusion_proof"]["audit_path"])
        index = receipt["inclusion_proof"]["leaf_index"]
        import hashlib

        def reconstruct(position, size):
            if size == 1:
                return hashlib.sha256(b"\x00" + encoded).digest()
            split = 1 << ((size - 1).bit_length() - 1)
            if position < split:
                left = reconstruct(position, split)
                right = next(path)
            else:
                right = reconstruct(position - split, size - split)
                left = next(path)
            return hashlib.sha256(b"\x01" + left + right).digest()

        assert reconstruct(index, count).hex() == receipt["batch"]["root"]
        assert list(path) == []


def test_receipt_unsealed_missing_and_invalid_id(database_client) -> None:
    client, _ = database_client
    saved = client.post("/registrations", json={"digest": "a" * 64}).json()
    assert client.get(f'/registrations/{saved["id"]}/receipt').status_code == 409
    assert client.get("/registrations/00000000-0000-0000-0000-000000000000/receipt").status_code == 404
    assert client.get("/registrations/invalid/receipt").status_code == 422


@pytest.mark.parametrize("corrupt", ["registration", "root", "size", "version"])
def test_inconsistent_stored_evidence_refused(database_client, corrupt) -> None:
    client, connection = database_client
    registration = sealed_registrations(client, connection, 2)[0]
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        record = session.get(Registration, UUID(registration["id"]))
        from sqlalchemy import select
        batch = session.scalar(select(MerkleBatch))
        # Change only the in-memory view; do not disable database integrity guards.
        if corrupt == "registration":
            record.digest = "f" * 64
        elif corrupt == "root":
            batch.root = "f" * 64
        elif corrupt == "size":
            batch.tree_size = 3
        else:
            batch.merkle_version = "unknown"
        with session.no_autoflush:
            with pytest.raises(ValueError):
                build_receipt(session, record.id)


def test_receipt_database_failure_is_generic(client) -> None:
    class FailedSession:
        def get(self, *args):
            raise OperationalError("private URL", {}, Exception("password"))

    client.app.dependency_overrides[get_session] = lambda: FailedSession()
    response = client.get("/registrations/00000000-0000-0000-0000-000000000001/receipt")
    assert response.status_code == 503
    assert response.json() == {"detail": "Receipt could not be generated"}
