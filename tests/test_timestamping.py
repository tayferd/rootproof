"""Verify a public synthetic RFC 3161 fixture without external requests."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
import httpx
import pytest
import rfc3161_client as tsp

from clients.timestamp import (
    TSA_URL, batch_commitment, main, request_timestamp,
    trusted_certificates, verify_timestamp,
)

FIXTURES = Path(__file__).parent / "fixtures"
EVIDENCE = FIXTURES / "freetsa-public-demo"


@pytest.fixture
def evidence():
    return (
        (EVIDENCE / "commitment.json").read_bytes(),
        (EVIDENCE / "response.tsr").read_bytes(),
        json.loads((EVIDENCE / "request-metadata.json").read_bytes())["nonce"],
    )


def test_signed_timestamp_verifies_under_explicit_trust(evidence) -> None:
    commitment, reply, nonce = evidence
    assert commitment == batch_commitment((FIXTURES / "timestamp-demo-receipt.json").read_bytes())
    result = verify_timestamp(commitment, reply, nonce)
    assert result["status"] == "single_authority_signature_valid"
    assert result["provider"] == "freetsa"
    assert result["authority_count"] == 1
    assert result["quorum_met"] is False
    assert result["revocation_checked"] is False
    assert result["timing_accuracy_policy_approved"] is False


@pytest.mark.parametrize("alter", ["message", "signature", "nonce"])
def test_altered_signed_evidence_is_rejected(evidence, alter) -> None:
    commitment, reply, nonce = evidence
    if alter == "message":
        commitment += b"changed"
    elif alter == "signature":
        reply = reply[:-1] + bytes([reply[-1] ^ 1])
    else:
        nonce += 1
    with pytest.raises((ValueError, tsp.VerificationError)):
        verify_timestamp(commitment, reply, nonce)


def test_embedded_ca_cannot_override_trusted_root(evidence, monkeypatch) -> None:
    commitment, reply, nonce = evidence
    _, signer = trusted_certificates()
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "Unrelated test CA")])
    unrelated = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(datetime(2025, 1, 1, tzinfo=timezone.utc))
        .not_valid_after(datetime(2030, 1, 1, tzinfo=timezone.utc))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    monkeypatch.setattr("clients.timestamp.trusted_certificates", lambda: (unrelated, signer))
    with pytest.raises(tsp.VerificationError):
        verify_timestamp(commitment, reply, nonce)


def test_trust_files_cannot_be_replaced(tmp_path) -> None:
    (tmp_path / "ca.crt").write_bytes(b"replacement trust root")
    with pytest.raises(ValueError, match="trust certificate changed"):
        trusted_certificates(tmp_path)


@pytest.mark.parametrize("nonce", [0, -1, True, "1", 2**257])
def test_invalid_nonce(evidence, nonce) -> None:
    with pytest.raises(ValueError):
        verify_timestamp(evidence[0], evidence[1], nonce)


def test_http_request_contains_only_imprint_not_commitment(evidence) -> None:
    commitment, reply, _ = evidence
    sent = []

    def serve(request):
        sent.append(request)
        return httpx.Response(200, content=reply, headers={"Content-Type": "application/timestamp-reply"})

    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        query, returned, nonce = request_timestamp(commitment, client)
    assert len(sent) == 1
    assert sent[0].url == TSA_URL
    assert sent[0].headers["Content-Type"] == "application/timestamp-query"
    assert commitment not in sent[0].content
    assert b"rootproof.batch-commitment" not in query
    assert returned == reply
    assert nonce > 0


@pytest.mark.parametrize("status,content_type,contents", [
    (503, "application/timestamp-reply", b"unavailable"),
    (200, "text/html", b"not a token"),
    (200, "application/timestamp-reply", b"x" * 65537),
], ids=["unavailable", "wrong-content-type", "oversized-response"])
def test_http_failures_and_size_limit(evidence, status, content_type, contents) -> None:
    def serve(request):
        return httpx.Response(status, content=contents, headers={"Content-Type": content_type})

    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        with pytest.raises((ValueError, httpx.HTTPError)):
            request_timestamp(evidence[0], client)


def test_offline_verify_does_not_contact_provider(monkeypatch, capsys) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline timestamp verification must not access the network")

    monkeypatch.setattr("clients.timestamp.httpx.Client", forbidden)
    monkeypatch.setattr(sys, "argv", ["timestamp", "verify", str(FIXTURES / "timestamp-demo-receipt.json"), str(EVIDENCE)])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["quorum_met"] is False


def test_stamp_never_overwrites_evidence(tmp_path, monkeypatch, capsys) -> None:
    folder = tmp_path / "existing"
    folder.mkdir()
    sentinel = folder / "response.tsr"
    sentinel.write_bytes(b"existing evidence")
    monkeypatch.setattr(sys, "argv", ["timestamp", "stamp", str(FIXTURES / "timestamp-demo-receipt.json"), str(folder)])
    assert main() == 1
    assert sentinel.read_bytes() == b"existing evidence"


def test_receipt_changes_change_timestamp_commitment() -> None:
    data = json.loads((FIXTURES / "timestamp-demo-receipt.json").read_bytes())
    original = batch_commitment(json.dumps(data).encode())
    # Batch ID is now authenticated by the separate timestamp commitment.
    data["batch"]["id"] = "00000000-0000-0000-0000-000000000099"
    assert batch_commitment(json.dumps(data).encode()) != original
