"""Local document operations; only digests and chosen metadata reach the API."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
from uuid import UUID

import httpx

from clients.registrations import _unique_object
from integrity.hashing import hash_file
from integrity.verification import MAX_RECEIPT_BYTES, VerificationResult, verify_receipt


class DocumentError(ValueError):
    """An operation failed without exposing internal server errors."""


@dataclass(frozen=True)
class Fingerprint:
    path: Path
    digest: str


def fingerprint(path: Path) -> Fingerprint:
    return Fingerprint(path, hash_file(path))


class LocalAPI:
    """This pilot deliberately connects only to the local development API."""

    def __init__(self, transport: httpx.BaseTransport | None = None):
        self.transport = transport

    def request(self, method: str, path: str, payload: dict | None = None) -> bytes:
        try:
            with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10, trust_env=False, transport=self.transport) as client:
                with client.stream(method, path, json=payload, follow_redirects=False) as response:
                    messages = {
                        404: "Registration not found. Check the ID.",
                        409: "Awaiting batch processing. Ask the local operator to seal a batch, then refresh.",
                        422: "The service could not accept these registration details.",
                        503: "The local service could not complete the request. Check PostgreSQL and try again.",
                    }
                    if response.status_code not in (200, 201):
                        raise DocumentError(messages.get(response.status_code, "The local service returned an unexpected response."))
                    if response.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                        raise DocumentError("The local service returned an invalid response.")
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        if len(content) + len(chunk) > MAX_RECEIPT_BYTES:
                            raise DocumentError("The local service response exceeds the supported size.")
                        content.extend(chunk)
                    return bytes(content)
        except httpx.HTTPError:
            raise DocumentError("Cannot reach the local API. Start the Rootproof server and try again.") from None

    def registration(self, content: bytes, expected_id: UUID | None = None) -> dict:
        try:
            data = json.loads(content, object_pairs_hook=_unique_object)
            identifier = UUID(data["id"])
            if expected_id is not None and identifier != expected_id:
                raise ValueError("Wrong registration")
            if data["hash_algorithm"] != "sha256" or re.fullmatch(r"[0-9a-f]{64}", data["digest"]) is None:
                raise ValueError("Unsupported hash")
            if type(data["format_version"]) is not int or data["format_version"] != 1:
                raise ValueError("Unsupported version")
            if data["status"] not in ("pending_batch", "sealed_pending_witnesses"):
                raise ValueError("Unsupported evidence status")
            return data
        except (ValueError, KeyError, TypeError, AttributeError):
            raise DocumentError("The local service returned invalid registration details.") from None

    def register(self, selected: Fingerprint, include_name: bool) -> dict:
        if hash_file(selected.path) != selected.digest:
            raise DocumentError("The file changed after hashing. Choose it again to refresh its fingerprint.")
        metadata = {"document_name": selected.path.name} if include_name else {}
        result = self.registration(self.request("POST", "/registrations", {
            "digest": selected.digest, "hash_algorithm": "sha256", "registration_metadata": metadata,
        }))
        if result["digest"] != selected.digest:
            raise DocumentError("The saved digest differs from the selected fingerprint.")
        return result

    def lookup(self, identifier: UUID) -> dict:
        return self.registration(self.request("GET", f"/registrations/{identifier}"), identifier)

    def receipt(self, identifier: UUID) -> bytes:
        content = self.request("GET", f"/registrations/{identifier}/receipt")
        try:
            data = json.loads(content)
            checked = verify_receipt(data["registration"]["digest"], content)
            if checked.registration_id != str(identifier) or not checked.inclusion_valid:
                raise ValueError("Inconsistent receipt")
        except (ValueError, KeyError, TypeError):
            raise DocumentError("The local service returned an invalid inclusion receipt.") from None
        return content


def verify_document(path: Path, receipt_path: Path) -> VerificationResult:
    with receipt_path.open("rb") as source:
        content = source.read(MAX_RECEIPT_BYTES + 1)
    return verify_receipt(hash_file(path), content)
