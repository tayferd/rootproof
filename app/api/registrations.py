"""Accept bounded JSON hash registrations; never accept source documents."""

from collections.abc import Iterator
import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from sqlalchemy import select
from app.db.models import BatchEntry, Registration
from app.schemas.registrations import RegistrationCreate, RegistrationResponse
from integrity.commitments import encode_registration

router = APIRouter()
MAX_REQUEST_BYTES = 32768


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object keys")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError("Nonfinite JSON numbers are not accepted")


async def parse_registration(request: Request) -> RegistrationCreate:
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(415, "Use application/json with a digest and selected metadata")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_REQUEST_BYTES:
            raise HTTPException(413, "Registration request exceeds 32768 bytes")
        body.extend(chunk)
    try:
        data = json.loads(body.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
        return RegistrationCreate.model_validate(data)
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        # Do not echo submitted metadata, file contents, or raw parsing errors.
        raise HTTPException(422, "Invalid digest or registration metadata") from None


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.database_engine) as session:
        yield session


@router.get("/registrations/{registration_id}", response_model=RegistrationResponse)
def retrieve(
    registration_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> RegistrationResponse:
    try:
        record = session.get(Registration, registration_id)
        if record is None:
            raise HTTPException(404, "Registration not found")
        entry = session.scalar(select(BatchEntry).where(BatchEntry.registration_id == registration_id))
        return RegistrationResponse(
            id=record.id, digest=record.digest, hash_algorithm=record.hash_algorithm,
            registration_metadata=record.registration_metadata,
            received_at=record.received_at, format_version=record.format_version,
            status="sealed_pending_witnesses" if entry else "pending_batch",
            batch_id=entry.batch_id if entry else None,
            batch_position=entry.position if entry else None,
        )
    except SQLAlchemyError:
        raise HTTPException(503, "Registration could not be retrieved") from None


@router.post(
    "/registrations",
    status_code=201,
    response_model=RegistrationResponse,
    openapi_extra={"requestBody": {"required": True, "content": {
        "application/json": {"schema": RegistrationCreate.model_json_schema()}
    }}},
)
def register(
    payload: Annotated[RegistrationCreate, Depends(parse_registration)],
    session: Annotated[Session, Depends(get_session)],
) -> RegistrationResponse:
    try:
        with session.begin():
            record = Registration(**payload.model_dump())
            session.add(record)
            session.flush()
            session.refresh(record)
            # Verify the database representation remains encodable before committing.
            encode_registration(
                registration_id=record.id, digest=record.digest,
                received_at=record.received_at, registration_metadata=record.registration_metadata,
                hash_algorithm=record.hash_algorithm, format_version=record.format_version,
            )
            response = RegistrationResponse(
                id=record.id, digest=record.digest, hash_algorithm=record.hash_algorithm,
                registration_metadata=record.registration_metadata,
                received_at=record.received_at, format_version=record.format_version,
            )
        return response
    except IntegrityError as error:
        if getattr(getattr(error.orig, "diag", None), "constraint_name", None) == "ck_registrations_metadata_size":
            raise HTTPException(422, "Metadata exceeds PostgreSQL's 8192-byte size limit") from None
        raise HTTPException(503, "Registration could not be saved") from None
    except SQLAlchemyError:
        raise HTTPException(503, "Registration could not be saved") from None
    except (ValueError, UnicodeError, OverflowError, RecursionError):
        raise HTTPException(422, "Registration metadata cannot be encoded") from None
