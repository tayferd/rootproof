"""Portable, offline single-authority evidence packages; no network operations."""

import argparse
import base64
from dataclasses import asdict
import json
from pathlib import Path

import rfc3161_client as tsp

from clients.timestamp import batch_commitment, read_bounded, verify_timestamp
from integrity.hashing import hash_file
from integrity.verification import MAX_RECEIPT_BYTES, verify_receipt

VERSION = "rootproof.evidence.freetsa.v1"
MAX_PACKAGE_BYTES = 200000


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate evidence fields")
        result[key] = value
    return result


def unpack(package: bytes):
    if len(package) > MAX_PACKAGE_BYTES:
        raise ValueError("Evidence package exceeds size limit")
    data = json.loads(package, object_pairs_hook=unique_object)
    if not isinstance(data, dict) or set(data) != {"evidence_version", "receipt_base64", "response_base64", "nonce"}:
        raise ValueError("Unexpected evidence package fields")
    if data["evidence_version"] != VERSION:
        raise ValueError("Unsupported evidence version")
    receipt = base64.b64decode(data["receipt_base64"], validate=True)
    response = base64.b64decode(data["response_base64"], validate=True)
    return receipt, response, data["nonce"]


def verify_package(digest: str, package: bytes) -> dict:
    receipt, response, nonce = unpack(package)
    registration = verify_receipt(digest, receipt)
    authority = verify_timestamp(batch_commitment(receipt), response, nonce)
    return {
        "status": "file_and_single_authority_signature_valid" if registration.file_matches and registration.inclusion_valid else "failed",
        "registration": asdict(registration),
        "timestamp": authority,
        "scope": "Authority time applies to the batch commitment; earlier server times are not authenticated.",
    }


def export_package(receipt: bytes, folder: Path) -> bytes:
    commitment = batch_commitment(receipt)
    if read_bounded(folder / "commitment.json", 4096) != commitment:
        raise ValueError("Timestamp evidence belongs to a different batch")
    metadata = json.loads(read_bounded(folder / "request-metadata.json", 4096), object_pairs_hook=unique_object)
    response = read_bounded(folder / "response.tsr", 65536)
    verify_timestamp(commitment, response, metadata["nonce"])
    return (json.dumps({
        "evidence_version": VERSION,
        "receipt_base64": base64.b64encode(receipt).decode("ascii"),
        "response_base64": base64.b64encode(response).decode("ascii"),
        "nonce": metadata["nonce"],
    }, indent=2) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("receipt", type=Path)
    export.add_argument("evidence_directory", type=Path)
    export.add_argument("output", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("document", type=Path)
    verify.add_argument("package", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "export":
            package = export_package(read_bounded(args.receipt, MAX_RECEIPT_BYTES), args.evidence_directory)
            with args.output.open("xb") as target:
                target.write(package)
            print("Saved single-authority evidence package. No external request was made.")
            return 0
        result = verify_package(hash_file(args.document), read_bounded(args.package, MAX_PACKAGE_BYTES))
        print(json.dumps(result))
        return 0 if result["status"] != "failed" else 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError, tsp.VerificationError):
        print("Evidence verification or export failed. Check the package, receipt, and trusted certificates.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
