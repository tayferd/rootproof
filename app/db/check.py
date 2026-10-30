"""Run with python -m app.db.check from the repository root."""

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.db.database import check_connection, create_database_engine


def main() -> int:
    try:
        settings = Settings()
    except ValidationError:
        print("Invalid configuration. Set DATABASE_URL in the environment or .env.")
        return 1

    engine = create_database_engine(settings)
    try:
        check_connection(engine)
    except SQLAlchemyError:
        print("PostgreSQL connection failed. Check the local service and connection settings.")
        return 1
    finally:
        engine.dispose()
    print("PostgreSQL connection successful.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
