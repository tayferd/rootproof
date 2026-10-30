"""Version 1 registration encoding using RFC 8785 canonical JSON."""

from datetime import datetime, timezone
import math
import re
from typing import Any
from uuid import UUID

import rfc8785


def validate_metadata(value: Any, *, depth: int = 0) -> None:
    """Keep JSON values reproducible after a PostgreSQL JSONB round trip."""
    if depth > 32:
        raise ValueError("Metadata nesting exceeds 32 levels")
    if isinstance(value, str):
        if "\x00" in value:
            raise ValueError("Metadata strings cannot contain NUL characters")
    elif value is None or isinstance(value, bool):
        return
    elif isinstance(value, (int, float)):
        if abs(value) > 2**53 - 1 or not math.isfinite(value):
            raise ValueError("Use strings for large or nonfinite metadata numbers")
    elif isinstance(value, list):
        for item in value:
            validate_metadata(item, depth=depth + 1)
    elif isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Metadata object keys must be strings")
            validate_metadata(key, depth=depth + 1)
            validate_metadata(item, depth=depth + 1)
    else:
        raise ValueError("Metadata must contain only JSON values")


def encode_registration(
    *,
    registration_id: UUID,
    digest: str,
    received_at: datetime,
    registration_metadata: dict[str, Any],
    hash_algorithm: str = "sha256",
    format_version: int = 1,
) -> bytes:
    if type(format_version) is not int or format_version != 1:
        raise ValueError("Unsupported registration format version")
    if hash_algorithm != "sha256" or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("Expected a lowercase SHA-256 hex digest")
    if not isinstance(registration_id, UUID):
        raise ValueError("Expected a UUID registration identifier")
    if received_at.tzinfo is None or received_at.utcoffset() is None:
        raise ValueError("Receipt time must include a timezone")
    if not isinstance(registration_metadata, dict):
        raise ValueError("Registration metadata must be a JSON object")
    validate_metadata(registration_metadata)
    return rfc8785.dumps({
        "type": "rootproof.registration",
        "format_version": format_version,
        "id": str(registration_id),
        "digest": digest,
        "hash_algorithm": hash_algorithm,
        "received_at": received_at.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "registration_metadata": registration_metadata,
    })
