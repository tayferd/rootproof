"""Check actual persistence, portable responses, invalid requests, and failures."""

from datetime import datetime
from contextlib import nullcontext
import json
import sys
from uuid import UUID

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.registrations import get_session
from app.config import Settings
from app.db.models import Registration
from app.main import create_app
from integrity.commitments import encode_registration
from integrity.hashing import hash_file
from clients.__main__ import main as client_main
from app.services.batching import seal_batch


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


def test_registration_is_persisted_and_encodable(database_client) -> None:
    client, connection = database_client
    payload = {"digest": "a" * 64, "registration_metadata": {"document_name": "example.pdf", "reading": 0.000001, "tags": [True, None]}}
    response = client.post("/registrations", json=payload)
    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "pending_batch"
    row = connection.execute(select(Registration.__table__)).mappings().one()
    assert str(row["id"]) == result["id"]
    assert row["digest"] == payload["digest"]
    assert row["registration_metadata"] == payload["registration_metadata"]
    assert encode_registration(
        registration_id=UUID(result["id"]), digest=result["digest"],
        received_at=datetime.fromisoformat(result["received_at"]),
        registration_metadata=result["registration_metadata"],
    ) == encode_registration(
        registration_id=row["id"], digest=row["digest"],
        received_at=row["received_at"], registration_metadata=row["registration_metadata"],
    )
    repeated = client.post("/registrations", json=payload)
    assert repeated.status_code == 201
    assert repeated.json()["id"] != result["id"]


@pytest.mark.parametrize("payload", [
    {}, {"digest": "invalid"}, {"digest": "A" * 64},
    {"digest": "a" * 64, "hash_algorithm": "md5"},
    {"digest": "a" * 64, "document_contents": "not accepted"},
    {"digest": "a" * 64, "received_at": "2000-01-01T00:00:00Z"},
    {"digest": "a" * 64, "registration_metadata": []},
    {"digest": "a" * 64, "registration_metadata": {"bad": 2**53}},
    {"digest": "a" * 64, "registration_metadata": {"bad": "\x00"}},
    {"digest": "a" * 64, "registration_metadata": {"bad": "\ud800"}},
    {"digest": "a" * 64, "registration_metadata": {"name": "x" * 8192}},
])
def test_invalid_input_is_rejected(client, payload) -> None:
    response = client.post("/registrations", content=json.dumps(payload), headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid digest or registration metadata"}


@pytest.mark.parametrize("body", [
    '{"digest":"' + "a" * 64 + '","digest":"' + "b" * 64 + '"}',
    '{"digest":"' + "a" * 64 + '","registration_metadata":{"a":1,"a":2}}',
    '{"digest":"' + "a" * 64 + '","registration_metadata":{"a":NaN}}',
    '{broken',
])
def test_ambiguous_or_invalid_json(client, body) -> None:
    assert client.post("/registrations", content=body, headers={"Content-Type": "application/json"}).status_code == 422


def test_body_limit_and_media_type(client) -> None:
    assert client.post("/registrations", content=b"x" * 32769, headers={"Content-Type": "application/json"}).status_code == 413
    assert client.post("/registrations", files={"file": ("file.txt", b"abc")}).status_code == 415


def test_postgresql_size_limit_rolls_back(database_client) -> None:
    client, connection = database_client
    # Canonical JSON omits spaces, whereas PostgreSQL JSONB text includes them.
    metadata = {"a": [0] * 3000}
    response = client.post("/registrations", json={"digest": "a" * 64, "registration_metadata": metadata})
    assert response.status_code == 422
    assert connection.scalar(select(func.count()).select_from(Registration)) == 0
    assert client.post("/registrations", json={"digest": "a" * 64}).status_code == 201


def test_database_failure_hides_details(client) -> None:
    class FailedSession:
        def begin(self):
            raise OperationalError("private database URL", {}, Exception("password"))

    client.app.dependency_overrides[get_session] = lambda: FailedSession()
    response = client.post("/registrations", json={"digest": "a" * 64})
    assert response.status_code == 503
    assert response.json() == {"detail": "Registration could not be saved"}


def test_retrieve_registration_and_unknown_identifier(database_client) -> None:
    client, _ = database_client
    created = client.post("/registrations", json={"digest": "a" * 64, "registration_metadata": {"document_name": "sample.txt"}})
    result = created.json()
    retrieved = client.get(f'/registrations/{result["id"]}')
    assert retrieved.status_code == 200
    assert retrieved.json() == result
    missing = client.get("/registrations/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Registration not found"}


def test_retrieve_invalid_id(client) -> None:
    assert client.get("/registrations/not-a-uuid").status_code == 422


def test_retrieve_database_failure_hides_details(client) -> None:
    class FailedSession:
        def get(self, *args):
            raise OperationalError("private URL", {}, Exception("password"))

    client.app.dependency_overrides[get_session] = lambda: FailedSession()
    response = client.get("/registrations/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 503
    assert response.json() == {"detail": "Registration could not be retrieved"}


def test_file_registration_retrieval_and_changed_file(database_client, tmp_path, monkeypatch, capsys) -> None:
    client, _ = database_client
    path = tmp_path / "experiment.txt"
    path.write_bytes(b"measurement=42\n")
    saved = client.post("/registrations", json={"digest": hash_file(path)})
    assert saved.status_code == 201
    identifier = saved.json()["id"]
    # Exercise CLI requests through the real API and PostgreSQL-backed session.
    monkeypatch.setattr("clients.__main__.httpx.Client", lambda **kwargs: nullcontext(client))
    monkeypatch.setattr(sys, "argv", ["clients", "compare", str(path), identifier])
    assert client_main() == 0
    assert '"comparison": "match"' in capsys.readouterr().out
    path.write_bytes(b"measurement=43\n")
    assert client_main() == 1
    assert '"comparison": "mismatch"' in capsys.readouterr().out


def test_registration_reports_sealed_batch_membership(database_client) -> None:
    client, connection = database_client
    saved = client.post("/registrations", json={"digest": "a" * 64}).json()
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        batch = seal_batch(session)
    result = client.get(f'/registrations/{saved["id"]}').json()
    assert result["status"] == "sealed_pending_witnesses"
    assert result["batch_id"] == str(batch.id)
    assert result["batch_position"] == 0
