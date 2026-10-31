"""Hash-only registration requests and pending registration responses."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
import rfc8785

from integrity.commitments import validate_metadata


class RegistrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    hash_algorithm: Literal["sha256"] = "sha256"
    registration_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("registration_metadata")
    @classmethod
    def portable_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        validate_metadata(value)
        if len(rfc8785.dumps(value)) > 8192:
            raise ValueError("Metadata exceeds size limit")
        return value


class RegistrationResponse(BaseModel):
    id: UUID
    digest: str
    hash_algorithm: Literal["sha256"]
    registration_metadata: dict[str, Any]
    received_at: datetime
    format_version: Literal[1]
    status: Literal["pending_batch", "sealed_pending_witnesses"] = "pending_batch"
    batch_id: UUID | None = None
    batch_position: int | None = None
