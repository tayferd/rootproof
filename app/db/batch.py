"""Local operator command: python -m app.db.batch --limit 1000."""

import argparse
from dataclasses import asdict
import json

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.database import create_database_engine
from app.services.batching import seal_batch


def main() -> int:
    parser = argparse.ArgumentParser(description="Seal pending registrations locally; no external witnessing")
    parser.add_argument("--limit", type=int, default=1000, choices=range(1, 1001), metavar="1..1000")
    args = parser.parse_args()
    try:
        settings = Settings()
    except ValidationError:
        print("Invalid DATABASE_URL configuration.")
        return 1
    engine = create_database_engine(settings)
    try:
        with Session(engine) as session:
            batch = seal_batch(session, limit=args.limit)
        output = {"status": "no_pending_registrations"} if batch is None else {
            **asdict(batch), "status": "sealed_pending_witnesses",
        }
        print(json.dumps(output, default=str))
        return 0
    except (SQLAlchemyError, ValueError, UnicodeError, RecursionError, OverflowError):
        print("Batch sealing failed; the transaction was rolled back. Check configuration and registrations.")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
