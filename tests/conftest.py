"""Database integration tests operate in disposable, rolled-back schemas."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, text

from app.config import Settings
from app.db.database import create_database_engine


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
