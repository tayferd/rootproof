"""Create database engines without connecting during module import."""

from sqlalchemy import Engine, create_engine, text

from app.config import Settings


def create_database_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 5},
    )


def check_connection(engine: Engine) -> None:
    with engine.connect() as connection:
        if connection.scalar(text("SELECT 1")) != 1:
            raise RuntimeError("Database connectivity check returned an unexpected result")
