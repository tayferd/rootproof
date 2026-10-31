"""Hash local files and compare them with database registrations."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from uuid import UUID

import httpx

from clients.registrations import fetch_digest
from integrity.hashing import hash_file
from integrity.verification import MAX_RECEIPT_BYTES, verify_receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Rootproof local tools; hash files without uploading them")
    commands = parser.add_subparsers(dest="command", required=True)
    hashing = commands.add_parser("hash", help="Calculate SHA-256 over exact file bytes")
    hashing.add_argument("path", type=Path)
    comparison = commands.add_parser("compare", help="Compare file bytes with a database registration; not a witnessed proof")
    comparison.add_argument("path", type=Path)
    comparison.add_argument("registration_id", type=UUID)
    comparison.add_argument("--api-url", default="http://127.0.0.1:8000")
    verification = commands.add_parser("verify", help="Verify a local file and receipt offline; no witness confirmation yet")
    verification.add_argument("path", type=Path)
    verification.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        digest = hash_file(args.path)
    except (OSError, ValueError) as error:
        print(f"Hashing failed: {error}", file=sys.stderr)
        return 1 if args.command == "hash" else 2
    if args.command == "verify":
        try:
            with args.receipt.open("rb") as source:
                receipt_bytes = source.read(MAX_RECEIPT_BYTES + 1)
            result = verify_receipt(digest, receipt_bytes)
        except (OSError, ValueError) as error:
            print(f"Verification failed: {error}", file=sys.stderr)
            return 2
        print(json.dumps(asdict(result)))
        return 0 if result.status == "valid_unwitnessed" else 1
    if args.command == "compare":
        try:
            with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
                expected = fetch_digest(client, args.api_url, args.registration_id)
        except ValueError as error:
            print(f"Comparison failed: {error}", file=sys.stderr)
            return 2
        matches = digest == expected
        print(json.dumps({
            "registration_id": str(args.registration_id),
            "comparison": "match" if matches else "mismatch",
            "basis": "database_registration_only",
            "file_digest": digest,
            "registered_digest": expected,
        }))
        return 0 if matches else 1
    print(json.dumps({"hash_algorithm": "sha256", "digest": digest}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
