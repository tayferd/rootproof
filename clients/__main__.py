"""Hash local files and compare them with database registrations."""

import argparse
import json
from pathlib import Path
import sys
from uuid import UUID

import httpx

from clients.registrations import fetch_digest
from integrity.hashing import hash_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Rootproof local tools; hash files without uploading them")
    commands = parser.add_subparsers(dest="command", required=True)
    hashing = commands.add_parser("hash", help="Calculate SHA-256 over exact file bytes")
    hashing.add_argument("path", type=Path)
    comparison = commands.add_parser("compare", help="Compare file bytes with a database registration; not a witnessed proof")
    comparison.add_argument("path", type=Path)
    comparison.add_argument("registration_id", type=UUID)
    comparison.add_argument("--api-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    try:
        digest = hash_file(args.path)
    except (OSError, ValueError) as error:
        print(f"Hashing failed: {error}", file=sys.stderr)
        return 1 if args.command == "hash" else 2
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
