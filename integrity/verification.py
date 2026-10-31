"""Strict offline receipt verification with no API, database, or environment access."""

from dataclasses import dataclass
from datetime import datetime
import json
import re
from uuid import UUID

from integrity.commitments import encode_registration
from integrity.merkle import MERKLE_VERSION
from integrity.proofs import PROOF_VERSION, verify_inclusion

MAX_RECEIPT_BYTES = 65536


class InvalidReceipt(ValueError):
    """The receipt is malformed or uses unsupported rules."""


@dataclass(frozen=True)
class VerificationResult:
    registration_id: str
    file_matches: bool
    inclusion_valid: bool
    status: str
    basis: str = "supplied_receipt_root"
    witness_status: str = "not_verified"


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON keys")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("Nonfinite JSON value")


def _fields(value: object, names: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError("Unexpected receipt fields")
    return value


def _uuid(value: object) -> UUID:
    if not isinstance(value, str):
        raise ValueError("Expected UUID string")
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError("Expected canonical UUID string")
    return parsed


def _digest(value: object) -> bytes:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Expected SHA-256 hexadecimal digest")
    return bytes.fromhex(value)


def _timestamp(value: object) -> datetime:
    pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)"
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise ValueError("Expected timezone-aware timestamp with microsecond precision or less")
    return datetime.fromisoformat(value)


def verify_receipt(file_digest: str, receipt_bytes: bytes) -> VerificationResult:
    """A valid result establishes consistency with this receipt's untrusted root."""
    try:
        _digest(file_digest)
        if not isinstance(receipt_bytes, bytes) or len(receipt_bytes) > MAX_RECEIPT_BYTES:
            raise ValueError("Receipt exceeds size limit")
        data = _fields(json.loads(
            receipt_bytes.decode("utf-8"), object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        ), {"receipt_version", "registration", "batch", "inclusion_proof", "status"})
        if data["receipt_version"] != "rootproof.receipt.v1" or data["status"] != "sealed_pending_witnesses":
            raise ValueError("Unsupported receipt version or witness state")
        registration = _fields(data["registration"], {
            "type", "id", "digest", "hash_algorithm", "received_at", "registration_metadata", "format_version",
        })
        if registration["type"] != "rootproof.registration":
            raise ValueError("Unsupported registration type")
        identifier = _uuid(registration["id"])
        _digest(registration["digest"])
        encoded = encode_registration(
            registration_id=identifier, digest=registration["digest"],
            received_at=_timestamp(registration["received_at"]),
            registration_metadata=registration["registration_metadata"],
            hash_algorithm=registration["hash_algorithm"], format_version=registration["format_version"],
        )
        batch = _fields(data["batch"], {"id", "root", "tree_size", "merkle_version", "sealed_at"})
        _uuid(batch["id"])
        _timestamp(batch["sealed_at"])
        root = _digest(batch["root"])
        size = batch["tree_size"]
        if type(size) is not int or not 1 <= size <= 1000 or batch["merkle_version"] != MERKLE_VERSION:
            raise ValueError("Unsupported batch")
        proof = _fields(data["inclusion_proof"], {"version", "leaf_index", "audit_path"})
        index, nodes = proof["leaf_index"], proof["audit_path"]
        if proof["version"] != PROOF_VERSION or type(index) is not int or not 0 <= index < size:
            raise ValueError("Unsupported proof or index")
        if not isinstance(nodes, list) or len(nodes) > 10:
            raise ValueError("Invalid proof path")
        path = [_digest(node) for node in nodes]
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
        raise InvalidReceipt("Receipt is malformed or uses an unsupported format") from None
    matches = file_digest == registration["digest"]
    included = verify_inclusion(encoded, index, size, path, root)
    return VerificationResult(
        str(identifier), matches, included,
        "valid_unwitnessed" if matches and included else "failed",
    )
