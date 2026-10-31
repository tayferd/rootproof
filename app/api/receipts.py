"""Export a receipt with no document contents or witness claims."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.registrations import get_session
from app.schemas.receipts import Receipt
from app.services.receipts import UnsealedRegistration, build_receipt

router = APIRouter()


@router.get("/registrations/{registration_id}/receipt", response_model=Receipt)
def download_receipt(
    registration_id: UUID,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> Receipt:
    try:
        receipt = build_receipt(session, registration_id)
    except UnsealedRegistration:
        raise HTTPException(409, "Registration is not in a sealed batch") from None
    except (SQLAlchemyError, ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise HTTPException(503, "Receipt could not be generated") from None
    if receipt is None:
        raise HTTPException(404, "Registration not found")
    response.headers["Content-Disposition"] = f'attachment; filename="rootproof-{registration_id}.json"'
    response.headers["Cache-Control"] = "no-store"
    return receipt
