"""Batch ordering, reproducibility, atomicity, and database immutability."""

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

from alembic import command
import pytest
from sqlalchemy import create_engine, delete, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import BatchEntry, MerkleBatch, Registration
from app.services.batching import seal_batch
from integrity.merkle import MERKLE_VERSION, merkle_root


def session_for(connection):
    return Session(bind=connection, join_transaction_mode="create_savepoint")


def add_registrations(connection, count=3):
    for index in reversed(range(count)):
        connection.execute(insert(Registration).values(
            id=UUID(int=index + 1), digest=f"{index:064x}",
            received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ))


def seal(connection, limit=1000):
    with session_for(connection) as session:
        result = seal_batch(session, limit=limit)
    # Exercise commit-time completeness checks inside the isolated test transaction.
    connection.execute(text("SET CONSTRAINTS rootproof_batch_complete IMMEDIATE"))
    connection.execute(text("SET CONSTRAINTS rootproof_batch_complete DEFERRED"))
    return result


def test_batch_order_root_and_no_duplicate_assignment(migrated_database) -> None:
    connection, _ = migrated_database
    add_registrations(connection)
    first = seal(connection, 2)
    entries = connection.execute(select(BatchEntry.__table__).where(BatchEntry.batch_id == first.id).order_by(BatchEntry.position)).mappings().all()
    assert [entry["registration_id"] for entry in entries] == [UUID(int=1), UUID(int=2)]
    assert [entry["position"] for entry in entries] == [0, 1]
    assert merkle_root([entry["entry_bytes"] for entry in entries]).hex() == first.root
    assert first.tree_size == 2
    assert first.sealed_at.tzinfo is not None
    second = seal(connection)
    assert second.id != first.id
    assert second.tree_size == 1
    assert seal(connection) is None
    assert connection.scalar(select(func.count()).select_from(MerkleBatch)) == 2
    assert connection.scalar(select(func.count()).select_from(BatchEntry)) == 3


def test_empty_batch_not_created(migrated_database) -> None:
    connection, _ = migrated_database
    assert seal(connection) is None
    assert connection.scalar(select(func.count()).select_from(MerkleBatch)) == 0


def test_targeted_sealing_leaves_other_registrations_pending(migrated_database) -> None:
    connection, _ = migrated_database
    add_registrations(connection, 3)
    with session_for(connection) as session:
        batch = seal_batch(session, registration_id=UUID(int=2))
    assert batch.tree_size == 1
    assert connection.scalars(select(BatchEntry.registration_id)).all() == [UUID(int=2)]
    with session_for(connection) as session:
        assert seal_batch(session, registration_id=UUID(int=2)) is None
    assert connection.scalar(select(func.count()).select_from(MerkleBatch)) == 1


@pytest.mark.parametrize("operation", ["batch_update", "batch_delete", "entry_update", "entry_delete", "record_update", "record_delete", "truncate"])
def test_sealed_data_is_immutable(migrated_database, operation) -> None:
    connection, _ = migrated_database
    add_registrations(connection, 1)
    batch = seal(connection)
    operations = {
        "batch_update": update(MerkleBatch).values(root="b" * 64),
        "batch_delete": delete(MerkleBatch),
        "entry_update": update(BatchEntry).values(entry_bytes=b"replacement"),
        "entry_delete": delete(BatchEntry),
        "record_update": update(Registration).values(digest="b" * 64),
        "record_delete": delete(Registration),
        "truncate": text("TRUNCATE merkle_batches, batch_entries, registrations"),
    }
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(operations[operation])
    assert connection.scalar(select(MerkleBatch.root).where(MerkleBatch.id == batch.id)) == batch.root


def test_late_entry_rejected(migrated_database) -> None:
    connection, _ = migrated_database
    add_registrations(connection, 2)
    batch = seal(connection, 1)
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(insert(BatchEntry).values(batch_id=batch.id, position=1, registration_id=UUID(int=2), entry_bytes=b"extra"))


def test_incomplete_batch_cannot_commit(migrated_database) -> None:
    connection, _ = migrated_database
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(insert(MerkleBatch).values(root="a" * 64, tree_size=1, merkle_version=MERKLE_VERSION))
            connection.execute(text("SET CONSTRAINTS rootproof_batch_complete IMMEDIATE"))
    assert connection.scalar(select(func.count()).select_from(MerkleBatch)) == 0


def test_bad_registration_rolls_back_entire_batch(migrated_database) -> None:
    connection, _ = migrated_database
    add_registrations(connection, 2)
    connection.execute(update(Registration).where(Registration.id == UUID(int=2)).values(registration_metadata={"number": 2**53}))
    with session_for(connection) as session:
        with pytest.raises(ValueError):
            seal_batch(session)
    assert connection.scalar(select(func.count()).select_from(MerkleBatch)) == 0
    assert connection.scalar(select(func.count()).select_from(BatchEntry)) == 0


def test_batch_migration_can_be_reversed(migrated_database) -> None:
    connection, config = migrated_database
    add_registrations(connection, 1)
    seal(connection)
    command.downgrade(config, "0001")
    assert connection.scalar(select(func.count()).select_from(Registration)) == 1
    command.upgrade(config, "head")
    assert connection.scalar(select(func.count()).select_from(MerkleBatch)) == 0


@pytest.mark.parametrize("limit", [0, 1001, True])
def test_invalid_limits(migrated_database, limit) -> None:
    connection, _ = migrated_database
    with session_for(connection) as session:
        with pytest.raises(ValueError):
            seal_batch(session, limit=limit)


def test_concurrent_sealers_commit_disjoint_batches(migrated_database) -> None:
    connection, config = migrated_database
    base_engine = connection.engine
    schema = "batch_concurrency_" + uuid4().hex
    # Separate committed test schema is required for visibility across connections.
    with base_engine.begin() as setup:
        setup.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(base_engine.url, connect_args={"options": f"-csearch_path={schema}", "connect_timeout": 5})
    try:
        with engine.begin() as setup:
            config.attributes["connection"] = setup
            command.upgrade(config, "head")
            add_registrations(setup, 4)
        barrier = Barrier(2)

        def worker():
            barrier.wait(timeout=10)
            with Session(engine) as session:
                return seal_batch(session, limit=2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(worker) for _ in range(2)]
            batches = [future.result(timeout=20) for future in futures]
        assert all(batch.tree_size == 2 for batch in batches)
        assert batches[0].id != batches[1].id
        with engine.connect() as check:
            assert check.scalar(select(func.count()).select_from(BatchEntry)) == 4
            assert check.scalar(select(func.count(func.distinct(BatchEntry.registration_id)))) == 4
            assert check.scalar(select(func.count()).select_from(MerkleBatch)) == 2
    finally:
        engine.dispose()
        # Remove only the uniquely named schema created above, never public data.
        with base_engine.begin() as cleanup:
            cleanup.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def test_partial_insert_failure_rolls_back(migrated_database, monkeypatch) -> None:
    connection, _ = migrated_database
    add_registrations(connection, 2)
    from sqlalchemy.exc import SQLAlchemyError

    with session_for(connection) as session:
        real_flush = session.flush
        count = 0

        def failing_flush(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 3:
                raise SQLAlchemyError("Simulated entry insert failure")
            return real_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", failing_flush)
        with pytest.raises(SQLAlchemyError):
            seal_batch(session)
    assert connection.scalar(select(func.count()).select_from(MerkleBatch)) == 0
    assert connection.scalar(select(func.count()).select_from(BatchEntry)) == 0
