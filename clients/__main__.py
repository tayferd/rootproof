"""Run python -m clients hash PATH to print a local file digest."""

import argparse
import json
from pathlib import Path
import sys

from integrity.hashing import hash_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Rootproof local tools; hash files without uploading them")
    commands = parser.add_subparsers(dest="command", required=True)
    hashing = commands.add_parser("hash", help="Calculate SHA-256 over exact file bytes")
    hashing.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        digest = hash_file(args.path)
    except (OSError, ValueError) as error:
        print(f"Hashing failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"hash_algorithm": "sha256", "digest": digest}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
