"""Exercise health responses and the real database through the HTTP interface."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.main import create_app


def test_health_reports_success(monkeypatch: pytest.MonkeyPatch) -> None:
    checked = []
    monkeypatch.setattr("app.api.health.check_connection", checked.append)
    settings = Settings(_env_file=None, database_url="postgresql+psycopg://localhost/test")
    with TestClient(create_app(settings)) as client:
        response = client.get("/health")
        assert checked == [client.app.state.database_engine]
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_hides_connection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_connection(engine: object) -> None:
        raise OperationalError("secret connection details", {}, Exception("private password"))

    monkeypatch.setattr("app.api.health.check_connection", fail_connection)
    settings = Settings(_env_file=None, database_url="postgresql+psycopg://localhost/test")
    with TestClient(create_app(settings)) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "database": "unavailable"}


@pytest.mark.integration
def test_health_with_postgresql() -> None:
    if os.environ.get("ROOTPROOF_TEST_DATABASE") != "1":
        pytest.skip("Set ROOTPROOF_TEST_DATABASE=1 to test local PostgreSQL")
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
