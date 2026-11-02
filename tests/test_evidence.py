import base64
import json
from pathlib import Path

import pytest
import rfc3161_client as tsp

from clients.evidence import export_package, verify_package
from clients.document_workflow import DocumentError, evidence_display, verify_saved_evidence
from integrity.hashing import hash_file

FIXTURES = Path(__file__).parent / "fixtures"


def package():
    return export_package((FIXTURES / "timestamp-demo-receipt.json").read_bytes(), FIXTURES / "freetsa-public-demo")


def test_offline_package_verifies_file_proof_and_authority():
    result = verify_package(hash_file(FIXTURES / "timestamp-demo.txt"), package())
    assert result["status"] == "file_and_single_authority_signature_valid"
    assert result["timestamp"]["quorum_met"] is False
    assert result["timestamp"]["timing_accuracy_policy_approved"] is False


def test_changed_file_fails_even_with_valid_timestamp():
    result = verify_package("0" * 64, package())
    assert result["status"] == "failed"
    assert result["timestamp"]["status"] == "single_authority_signature_valid"


@pytest.mark.parametrize("alter", ["signature", "nonce", "version", "extra", "receipt"])
def test_tampered_package_rejected(alter):
    data = json.loads(package())
    if alter == "signature":
        token = base64.b64decode(data["response_base64"])
        data["response_base64"] = base64.b64encode(token[:-1] + bytes([token[-1] ^ 1])).decode()
    elif alter == "nonce":
        data["nonce"] += 1
    elif alter == "version":
        data["evidence_version"] = "unknown"
    elif alter == "extra":
        data["trusted_certificate"] = "attacker"
    else:
        receipt = json.loads(base64.b64decode(data["receipt_base64"]))
        receipt["batch"]["id"] = "00000000-0000-0000-0000-000000000001"
        data["receipt_base64"] = base64.b64encode(json.dumps(receipt).encode()).decode()
    with pytest.raises((ValueError, tsp.VerificationError)):
        verify_package("0" * 64, json.dumps(data).encode())


def test_duplicate_fields_rejected():
    data = package().decode().rstrip()
    with pytest.raises(ValueError, match="Duplicate"):
        verify_package("0" * 64, (data[:-1] + ',"nonce":1}').encode())


def test_desktop_checks_combined_evidence_without_network(tmp_path, monkeypatch):
    import httpx
    def no_network(*args, **kwargs):
        raise AssertionError("Offline verification attempted network access")
    monkeypatch.setattr(httpx.Client, "send", no_network)
    saved = tmp_path / "evidence.json"
    saved.write_bytes(package())
    result = verify_saved_evidence(FIXTURES / "timestamp-demo.txt", saved)
    heading, details = evidence_display(result)
    assert heading == "File, proof and authority signature match"
    assert result["timestamp"]["provider_time"] in details
    assert "quorum not met" in details
    assert "Revocation not checked" in details
    changed = tmp_path / "changed.txt"
    changed.write_bytes(b"changed document")
    heading, details = evidence_display(verify_saved_evidence(changed, saved))
    assert heading.startswith("Verification failed")
    assert "digest: No" in details


def test_desktop_receipts_still_report_unwitnessed():
    result = verify_saved_evidence(FIXTURES / "timestamp-demo.txt", FIXTURES / "timestamp-demo-receipt.json")
    heading, details = evidence_display(result)
    assert "unwitnessed" in heading
    assert "timestamp: not verified" in details


@pytest.mark.parametrize("alter", ["nonce", "version", "duplicate", "oversize"])
def test_desktop_invalid_package_has_no_success_or_receipt_fallback(tmp_path, alter):
    data = json.loads(package())
    if alter == "nonce":
        data["nonce"] += 1
    elif alter == "version":
        data["evidence_version"] = "unknown"
    content = json.dumps(data).encode()
    if alter == "duplicate":
        content = content[:-1] + b',"nonce":1}'
    elif alter == "oversize":
        content = b" " * 200001
    saved = tmp_path / "bad.json"
    saved.write_bytes(content)
    with pytest.raises(DocumentError):
        verify_saved_evidence(FIXTURES / "timestamp-demo.txt", saved)
