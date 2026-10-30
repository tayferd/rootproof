"""Configuration checks and an opt-in real PostgreSQL connectivity test."""

import os

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.db.database import check_connection, create_database_engine


@pytest.mark.parametrize("url", ["", "sqlite:///test.db", "postgresql://localhost/db", "postgresql+psycopg://localhost"])
def test_invalid_database_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=url)


def test_database_password_is_hidden_in_settings() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:private-test-password@localhost/test",
    )
    assert "private-test-password" not in repr(settings)


@pytest.mark.integration
def test_postgresql_connection() -> None:
    if os.environ.get("ROOTPROOF_TEST_DATABASE") != "1":
        pytest.skip("Set ROOTPROOF_TEST_DATABASE=1 to test the configured local PostgreSQL database")
    engine = create_database_engine(Settings())
    try:
        check_connection(engine)
    finally:
        engine.dispose()
