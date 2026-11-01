"""The desktop workflow hashes locally, exposes evidence limits, and sends no files."""

from pathlib import Path
import json
from uuid import UUID

import httpx
import pytest

from clients.document_workflow import DocumentError, LocalAPI, fingerprint, verify_document

FIXTURES = Path(__file__).parent / "fixtures"
IDENTIFIER = UUID("00000000-0000-0000-0000-000000000001")


def response(digest):
    return {"id": str(IDENTIFIER), "digest": digest, "hash_algorithm": "sha256", "format_version": 1, "status": "pending_batch"}


@pytest.mark.parametrize("include_name", [True, False])
def test_registration_sends_only_digest_and_chosen_name(tmp_path, include_name) -> None:
    path = tmp_path / "private example.txt"
    path.write_bytes(b"confidential original document contents")
    selected = fingerprint(path)
    requests = []

    def server(request):
        requests.append(request)
        return httpx.Response(201, json=response(selected.digest))

    api = LocalAPI(httpx.MockTransport(server))
    saved = api.register(selected, include_name)
    assert saved["digest"] == selected.digest
    assert len(requests) == 1
    sent = requests[0]
    assert str(sent.url) == "http://127.0.0.1:8000/registrations"
    payload = json.loads(sent.content)
    assert payload == {"digest": selected.digest, "hash_algorithm": "sha256", "registration_metadata": {"document_name": path.name} if include_name else {}}
    assert b"confidential original document contents" not in sent.content
    assert str(tmp_path).encode() not in sent.content


def test_file_changed_after_preview_is_not_registered(tmp_path) -> None:
    path = tmp_path / "sample.txt"
    path.write_bytes(b"first version")
    selected = fingerprint(path)
    path.write_bytes(b"changed version")

    def forbidden(request):
        raise AssertionError("Changed file must not be sent as the original fingerprint")

    with pytest.raises(DocumentError, match="file changed"):
        LocalAPI(httpx.MockTransport(forbidden)).register(selected, False)


@pytest.mark.parametrize("code", [404, 409, 422, 503])
def test_service_failure_has_clear_message(code) -> None:
    api = LocalAPI(httpx.MockTransport(lambda request: httpx.Response(code, json={"detail": "private internal details"})))
    with pytest.raises(DocumentError) as caught:
        api.lookup(IDENTIFIER)
    assert "private internal details" not in str(caught.value)


def test_unavailable_service_has_clear_message() -> None:
    def unavailable(request):
        raise httpx.ConnectError("internal network error")

    with pytest.raises(DocumentError, match="Cannot reach the local API"):
        LocalAPI(httpx.MockTransport(unavailable)).lookup(IDENTIFIER)


def test_lookup_and_receipt_are_consistent() -> None:
    receipt_bytes = (FIXTURES / "timestamp-demo-receipt.json").read_bytes()
    receipt = json.loads(receipt_bytes)
    digest = receipt["registration"]["digest"]

    def server(request):
        assert request.method == "GET"
        if request.url.path.endswith("/receipt"):
            return httpx.Response(200, content=receipt_bytes, headers={"Content-Type": "application/json"})
        return httpx.Response(200, json=response(digest))

    api = LocalAPI(httpx.MockTransport(server))
    assert api.lookup(IDENTIFIER)["id"] == str(IDENTIFIER)
    assert api.receipt(IDENTIFIER) == receipt_bytes
    with pytest.raises(DocumentError):
        api.receipt(UUID(int=99))


def test_offline_document_check_needs_no_service(tmp_path, monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline check must not create an HTTP client")

    monkeypatch.setattr("clients.document_workflow.httpx.Client", forbidden)
    original = FIXTURES / "timestamp-demo.txt"
    receipt = FIXTURES / "timestamp-demo-receipt.json"
    assert verify_document(original, receipt).status == "valid_unwitnessed"
    changed = tmp_path / "changed.txt"
    changed.write_bytes(original.read_bytes() + b"changed")
    assert verify_document(changed, receipt).status == "failed"


def test_oversized_response_rejected() -> None:
    api = LocalAPI(httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 65537, headers={"Content-Type": "application/json"})))
    with pytest.raises(DocumentError, match="exceeds"):
        api.lookup(IDENTIFIER)


def test_registration_details_are_explained_before_reading_document(tmp_path) -> None:
    details = tmp_path / "registration.json"
    details.write_text(json.dumps(response("a" * 64)), encoding="utf-8")
    # A mistaken JSON selection must be explained without reading the document.
    with pytest.raises(DocumentError, match="registration details, not an inclusion receipt"):
        verify_document(tmp_path / "unopened-document.docx", details)
