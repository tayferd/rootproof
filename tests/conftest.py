"""Database integration tests operate in disposable, rolled-back schemas."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, text
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.api.registrations import get_session
from app.config import Settings
from app.db.database import create_database_engine
from app.main import create_app


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


@pytest.fixture
def client():
    settings = Settings(_env_file=None, database_url="postgresql+psycopg://localhost/test")
    with TestClient(create_app(settings)) as value:
        yield value


@pytest.fixture
def database_client(migrated_database, client):
    connection, _ = migrated_database

    def test_session():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session

    client.app.dependency_overrides[get_session] = test_session
    yield client, connection
