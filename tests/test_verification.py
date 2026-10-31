"""Offline verification must distinguish consistency from external witnessing."""

from datetime import datetime, timezone
import hashlib
import json
import sys
from uuid import UUID

import pytest

from clients.__main__ import main
from integrity.commitments import encode_registration
from integrity.merkle import MERKLE_VERSION, merkle_root
from integrity.proofs import PROOF_VERSION, inclusion_proof, verify_inclusion
from integrity.verification import InvalidReceipt, verify_receipt

DIGEST = hashlib.sha256(b"original file").hexdigest()


def sample_receipt():
    registration = {
        "type": "rootproof.registration", "id": "00000000-0000-0000-0000-000000000001",
        "digest": DIGEST, "hash_algorithm": "sha256", "format_version": 1,
        "received_at": "2026-01-01T00:00:00.000000Z", "registration_metadata": {"name": "example.txt"},
    }
    encoded = encode_registration(
        registration_id=UUID(registration["id"]), digest=DIGEST,
        received_at=datetime(2026, 1, 1, tzinfo=timezone.utc), registration_metadata={"name": "example.txt"},
    )
    entries = [b"other entry", b"second entry", encoded]
    return {
        "receipt_version": "rootproof.receipt.v1", "registration": registration,
        "batch": {
            "id": "00000000-0000-0000-0000-000000000002", "root": merkle_root(entries).hex(),
            "tree_size": 3, "merkle_version": MERKLE_VERSION, "sealed_at": "2026-01-01T00:01:00Z",
        },
        "inclusion_proof": {"version": PROOF_VERSION, "leaf_index": 2, "audit_path": [node.hex() for node in inclusion_proof(entries, 2)]},
        "status": "sealed_pending_witnesses",
    }


def serialize(receipt):
    return json.dumps(receipt).encode()


def test_offline_receipt_consistency_and_changed_file() -> None:
    receipt = serialize(sample_receipt())
    good = verify_receipt(DIGEST, receipt)
    assert good.status == "valid_unwitnessed"
    assert good.file_matches and good.inclusion_valid
    assert good.witness_status == "not_verified"
    assert good.basis == "supplied_receipt_root"
    changed = verify_receipt(hashlib.sha256(b"changed file").hexdigest(), receipt)
    assert changed.status == "failed"
    assert not changed.file_matches
    assert changed.inclusion_valid


@pytest.mark.parametrize("part,key,value", [
    ("registration", "registration_metadata", {"name": "changed.txt"}),
    ("registration", "digest", "b" * 64),
    ("registration", "received_at", "2026-01-02T00:00:00Z"),
    ("registration", "id", "00000000-0000-0000-0000-000000000009"),
    ("batch", "root", "f" * 64),
    ("inclusion_proof", "audit_path", ["f" * 64]),
    ("inclusion_proof", "audit_path", []),
    ("inclusion_proof", "audit_path", ["a" * 64, "b" * 64]),
])
def test_tampered_evidence_fails(part, key, value) -> None:
    receipt = sample_receipt()
    receipt[part][key] = value
    result = verify_receipt(DIGEST, serialize(receipt))
    assert result.status == "failed"
    assert not result.inclusion_valid


@pytest.mark.parametrize("part,key,value", [
    ("registration", "format_version", True),
    ("registration", "format_version", 2),
    ("registration", "hash_algorithm", "md5"),
    ("registration", "type", "unknown"),
    ("registration", "received_at", "2026-01-01T00:00:00"),
    ("registration", "received_at", "2026-01-01T00:00:00.0000001Z"),
    ("registration", "digest", "B" * 64),
    ("registration", "registration_metadata", {"large": 2**53}),
    ("batch", "tree_size", True), ("batch", "tree_size", 0), ("batch", "tree_size", 1001),
    ("batch", "merkle_version", "unknown"),
    ("batch", "root", "invalid"),
    ("inclusion_proof", "version", "unknown"),
    ("inclusion_proof", "leaf_index", True), ("inclusion_proof", "leaf_index", -1),
    ("inclusion_proof", "leaf_index", 3),
    ("inclusion_proof", "audit_path", ["not-a-hash"]),
])
def test_malformed_or_unsupported_receipt_rejected(part, key, value) -> None:
    receipt = sample_receipt()
    receipt[part][key] = value
    with pytest.raises(InvalidReceipt):
        verify_receipt(DIGEST, serialize(receipt))


def test_strict_json_and_size_limits() -> None:
    receipt = sample_receipt()
    valid = serialize(receipt)
    invalid = [
        b"{broken", b"[]", b"\xff", b" " * 65537,
        valid.replace(b'"receipt_version":', b'"receipt_version":"unknown","receipt_version":', 1),
    ]
    receipt["receipt_version"] = "future"
    invalid.append(serialize(receipt))
    receipt = sample_receipt()
    receipt["status"] = "witnessed"
    invalid.append(serialize(receipt))
    receipt = sample_receipt()
    receipt["extra"] = "unsupported"
    invalid.append(serialize(receipt))
    for content in invalid:
        with pytest.raises(InvalidReceipt):
            verify_receipt(DIGEST, content)


def test_descriptive_batch_fields_are_not_authenticated() -> None:
    receipt = sample_receipt()
    receipt["batch"]["id"] = "00000000-0000-0000-0000-000000000099"
    receipt["batch"]["sealed_at"] = "2020-01-01T00:00:00Z"
    result = verify_receipt(DIGEST, serialize(receipt))
    assert result.status == "valid_unwitnessed"
    assert result.witness_status == "not_verified"
    # Batch labels and time are descriptive; inclusion does not authenticate them.


def test_self_consistent_replacement_is_not_claimed_as_witnessed() -> None:
    receipt = sample_receipt()
    replacement_digest = "b" * 64
    receipt["registration"]["digest"] = replacement_digest
    encoded = encode_registration(
        registration_id=UUID(receipt["registration"]["id"]), digest=replacement_digest,
        received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        registration_metadata=receipt["registration"]["registration_metadata"],
    )
    receipt["batch"]["root"] = merkle_root([encoded]).hex()
    receipt["batch"]["tree_size"] = 1
    receipt["inclusion_proof"]["leaf_index"] = 0
    receipt["inclusion_proof"]["audit_path"] = []
    result = verify_receipt(replacement_digest, serialize(receipt))
    assert result.status == "valid_unwitnessed"
    assert result.witness_status == "not_verified"


def test_fixed_cross_runtime_proof_vector() -> None:
    assert verify_inclusion(
        b"\x02", 2, 3,
        [bytes.fromhex("a20bf9a7cc2dc8a08f5f415a71b19f6ac427bab54d24eec868b5d3103449953a")],
        bytes.fromhex("3b6cccd7e3e023ff393006f030315ee7ad9eb111b022b41fba7e5b7a3973f688"),
    )


@pytest.mark.parametrize("size", [1, 2, 3, 5, 7, 8, 9, 16, 17, 33, 1000])
def test_verifier_handles_odd_trees_and_boundaries(size) -> None:
    entries = [i.to_bytes(4, "big") for i in range(size)]
    root = merkle_root(entries)
    indexes = range(size) if size < 1000 else [0, 1, 499, 511, 512, 998, 999]
    for index in indexes:
        path = inclusion_proof(entries, index)
        assert verify_inclusion(entries[index], index, size, path, root)
        assert not verify_inclusion(entries[index], index, size, path + [b"a" * 32], root)


def test_cli_works_without_database_or_network(tmp_path, monkeypatch, capsys) -> None:
    path, receipt_path = tmp_path / "file.txt", tmp_path / "receipt.json"
    path.write_bytes(b"original file")
    receipt_path.write_bytes(serialize(sample_receipt()))

    def forbid_network(*args, **kwargs):
        raise AssertionError("Offline verification must not instantiate an HTTP client")

    monkeypatch.setattr("clients.__main__.httpx.Client", forbid_network)
    monkeypatch.setenv("DATABASE_URL", "deliberately-invalid")
    monkeypatch.setattr(sys, "argv", ["clients", "verify", str(path), str(receipt_path)])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "valid_unwitnessed"
    path.write_bytes(b"changed file")
    assert main() == 1
    assert json.loads(capsys.readouterr().out)["file_matches"] is False
    receipt_path.write_bytes(b"invalid JSON")
    assert main() == 2
    assert "Receipt is malformed" in capsys.readouterr().err


def test_real_export_can_be_verified_offline(database_client, tmp_path) -> None:
    from sqlalchemy.orm import Session
    from app.services.batching import seal_batch
    from integrity.hashing import hash_file

    client, connection = database_client
    path = tmp_path / "sample.bin"
    path.write_bytes(b"original file")
    identifier = client.post("/registrations", json={"digest": hash_file(path)}).json()["id"]
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        seal_batch(session)
    receipt = client.get(f"/registrations/{identifier}/receipt")
    assert receipt.status_code == 200
    result = verify_receipt(hash_file(path), receipt.content)
    assert result.status == "valid_unwitnessed"
    path.write_bytes(b"modified file")
    assert verify_receipt(hash_file(path), receipt.content).status == "failed"
