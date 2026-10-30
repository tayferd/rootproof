"""File comparisons must distinguish mismatches from unavailable evidence."""

import hashlib
from pathlib import Path
import sys
from uuid import UUID

import httpx
import pytest

from clients.__main__ import main
from clients.registrations import RegistrationLookupError, fetch_digest

REGISTRATION_ID = UUID("00000000-0000-0000-0000-000000000001")


def registration(**overrides):
    return {"id": str(REGISTRATION_ID), "digest": hashlib.sha256(b"abc").hexdigest(), "hash_algorithm": "sha256", "format_version": 1} | overrides


@pytest.mark.parametrize(("contents", "expected", "exit_code"), [
    (b"abc", "match", 0), (b"changed", "mismatch", 1),
])
def test_cli_comparison(tmp_path: Path, monkeypatch, capsys, contents, expected, exit_code) -> None:
    path = tmp_path / "file.txt"
    path.write_bytes(contents)
    requests = []

    def serve(request):
        requests.append(request)
        return httpx.Response(200, json=registration())

    client = httpx.Client(transport=httpx.MockTransport(serve))
    monkeypatch.setattr("clients.__main__.httpx.Client", lambda **kwargs: client)
    monkeypatch.setattr(sys, "argv", ["clients", "compare", str(path), str(REGISTRATION_ID)])
    assert main() == exit_code
    output = capsys.readouterr().out
    assert f'"comparison": "{expected}"' in output
    assert "database_registration_only" in output
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].content == b""
    assert requests[0].url.path == f"/registrations/{REGISTRATION_ID}"


@pytest.mark.parametrize("changes", [
    {"id": "00000000-0000-0000-0000-000000000002"},
    {"digest": "invalid"}, {"hash_algorithm": "md5"},
    {"format_version": 2}, {"format_version": True},
])
def test_malformed_registration_rejected(changes) -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=registration(**changes)))) as client:
        with pytest.raises(RegistrationLookupError):
            fetch_digest(client, "http://localhost", REGISTRATION_ID)


@pytest.mark.parametrize("status", [404, 503])
def test_unavailable_registration(status) -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status))) as client:
        with pytest.raises(RegistrationLookupError):
            fetch_digest(client, "http://localhost", REGISTRATION_ID)


def test_network_failure_is_error_not_mismatch(tmp_path, monkeypatch, capsys) -> None:
    path = tmp_path / "file.txt"
    path.write_bytes(b"abc")

    def fail(request):
        raise httpx.ConnectError("private network error")

    client = httpx.Client(transport=httpx.MockTransport(fail))
    monkeypatch.setattr("clients.__main__.httpx.Client", lambda **kwargs: client)
    monkeypatch.setattr(sys, "argv", ["clients", "compare", str(path), str(REGISTRATION_ID)])
    assert main() == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "Could not contact Rootproof" in output.err
    assert "private network error" not in output.err


def test_missing_local_file_is_error(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setattr(sys, "argv", ["clients", "compare", str(tmp_path / "missing"), str(REGISTRATION_ID)])
    assert main() == 2
    assert "Hashing failed" in capsys.readouterr().err
