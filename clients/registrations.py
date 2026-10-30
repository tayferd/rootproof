"""Read a stored digest for comparison, without sending file contents."""

import json
import re
from uuid import UUID

import httpx


class RegistrationLookupError(ValueError):
    """An unavailable or malformed registration cannot establish a comparison."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate response field")
        result[key] = value
    return result


def fetch_digest(client: httpx.Client, api_url: str, registration_id: UUID) -> str:
    try:
        with client.stream("GET", f"{api_url.rstrip('/')}/registrations/{registration_id}") as response:
            if response.status_code == 404:
                raise RegistrationLookupError("Registration not found")
            if response.status_code != 200:
                raise RegistrationLookupError("Rootproof could not return the registration")
            if response.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise RegistrationLookupError("Rootproof returned an invalid registration")
            body = bytearray()
            for chunk in response.iter_bytes():
                if len(body) + len(chunk) > 32768:
                    raise RegistrationLookupError("Registration response exceeds size limit")
                body.extend(chunk)
        data = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
        if not isinstance(data, dict) or UUID(data["id"]) != registration_id:
            raise ValueError("Wrong registration identifier")
        if data["hash_algorithm"] != "sha256" or type(data["format_version"]) is not int or data["format_version"] != 1:
            raise ValueError("Unsupported registration format")
        if not isinstance(data["digest"], str) or re.fullmatch(r"[0-9a-f]{64}", data["digest"]) is None:
            raise ValueError("Invalid SHA-256 digest")
        return data["digest"]
    except RegistrationLookupError:
        raise
    except (httpx.HTTPError, httpx.InvalidURL):
        raise RegistrationLookupError("Could not contact Rootproof; check the server and API URL") from None
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        raise RegistrationLookupError("Rootproof returned an invalid registration") from None
