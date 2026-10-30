"""Exercise migrations and database integrity in disposable transaction schemas."""

import os
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection, inspect, insert, text
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db.database import create_database_engine
from app.db.models import Base, Registration

pytestmark = pytest.mark.integration


@pytest.fixture
def migrated_database() -> Iterator[tuple[Connection, Config]]:
    if os.environ.get("ROOTPROOF_TEST_DATABASE") != "1":
        pytest.skip("Set ROOTPROOF_TEST_DATABASE=1 to test local PostgreSQL")
    engine = create_database_engine(Settings())
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                schema = "test_" + uuid4().hex
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                config = Config("alembic.ini")
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                yield connection, config
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_registration_defaults_and_repeat_digest(migrated_database) -> None:
    connection, _ = migrated_database
    first = connection.execute(
        insert(Registration).values(digest="a" * 64, registration_metadata={"document_name": "example.pdf"})
        .returning(*Registration.__table__.columns)
    ).mappings().one()
    second_id = connection.scalar(insert(Registration).values(digest="a" * 64).returning(Registration.id))
    assert isinstance(first["id"], UUID)
    assert first["id"] != second_id
    assert first["hash_algorithm"] == "sha256"
    assert first["format_version"] == 1
    assert first["received_at"].tzinfo is not None
    assert first["registration_metadata"] == {"document_name": "example.pdf"}


@pytest.mark.parametrize("values", [
    {"digest": "invalid"},
    {"digest": "A" * 64},
    {"digest": None},
    {"hash_algorithm": "md5"},
    {"format_version": 2},
    {"registration_metadata": []},
    {"registration_metadata": None},
    {"registration_metadata": {"name": "x" * 8192}},
])
def test_invalid_registrations_are_rejected(migrated_database, values) -> None:
    connection, _ = migrated_database
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(insert(Registration).values(**({"digest": "a" * 64} | values)))


def test_migration_matches_model_and_downgrades(migrated_database) -> None:
    connection, config = migrated_database
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    command.downgrade(config, "base")
    assert "registrations" not in inspect(connection).get_table_names()
    command.upgrade(config, "head")
    assert "registrations" in inspect(connection).get_table_names()
