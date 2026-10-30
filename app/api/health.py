"""Application and PostgreSQL readiness check."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import check_connection

router = APIRouter()


@router.get("/health")
def health(request: Request) -> JSONResponse:
    try:
        check_connection(request.app.state.database_engine)
    except (SQLAlchemyError, RuntimeError):
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "unavailable"},
        )
    return JSONResponse(content={"status": "ok", "database": "ok"})
