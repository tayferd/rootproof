"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router
from app.api.registrations import router as registrations_router
from app.config import Settings
from app.db.database import create_database_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(settings or Settings())
        application.state.database_engine = engine
        try:
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="Rootproof", lifespan=lifespan)
    application.include_router(router)
    application.include_router(registrations_router)
    return application


app = create_app()
