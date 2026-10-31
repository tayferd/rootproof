"""M-013 single-authority experiment, separate from production receipts and quorum."""

import argparse
import hashlib
import json
from pathlib import Path

from cryptography import x509
import httpx
import rfc3161_client as tsp
import rfc8785

from integrity.verification import MAX_RECEIPT_BYTES, verify_receipt

TSA_URL = "https://freetsa.org/tsr"
TRUST_DIRECTORY = Path(__file__).resolve().parents[1] / "trust" / "freetsa"
# SHA-256 of the exact PEM files published by FreeTSA, not DER fingerprints.
TRUST_FILE_HASHES = {
    "ca.crt": "2151b61137ffa86bf664691ba67e7da0b19f98c758e3d228d5d8ebf27e044438",
    "tsa.crt": "8bfb0305bb64e2571ca507552ef3245cb1c2fee8728e0ff8689225081ea13467",
}
MAX_RESPONSE_BYTES = 65536


def read_bounded(path: Path, maximum: int) -> bytes:
    with path.open("rb") as source:
        data = source.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("Evidence file exceeds size limit")
    return data


def batch_commitment(receipt_bytes: bytes) -> bytes:
    # The offline verifier supplies strict schema/duplicate-key checks. This
    # establishes consistency only; it does not authenticate the root's history.
    if not isinstance(receipt_bytes, bytes) or len(receipt_bytes) > MAX_RECEIPT_BYTES:
        raise ValueError("Receipt exceeds size limit")
    data = json.loads(receipt_bytes)
    result = verify_receipt(data["registration"]["digest"], receipt_bytes)
    if not result.inclusion_valid:
        raise ValueError("Receipt inclusion proof is invalid")
    batch = data["batch"]
    return rfc8785.dumps({
        "type": "rootproof.batch-commitment", "format_version": 1,
        "batch_id": batch["id"], "root": batch["root"],
        "tree_size": batch["tree_size"], "merkle_version": batch["merkle_version"],
    })


def trusted_certificates(directory: Path = TRUST_DIRECTORY):
    certificates = {}
    for name, expected in TRUST_FILE_HASHES.items():
        data = read_bounded(directory / name, 16384)
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Timestamp trust certificate changed; explicit review is required")
        certificates[name] = x509.load_pem_x509_certificate(data)
    return certificates["ca.crt"], certificates["tsa.crt"]


def verify_timestamp(commitment: bytes, response_bytes: bytes, nonce: int) -> dict:
    if type(nonce) is not int or nonce <= 0 or nonce.bit_length() > 256:
        raise ValueError("Invalid saved request nonce")
    if not 0 < len(response_bytes) <= MAX_RESPONSE_BYTES:
        raise ValueError("Invalid timestamp response size")
    root, signer = trusted_certificates()
    response = tsp.decode_timestamp_response(response_bytes)
    if response.tst_info.message_imprint.hash_algorithm.dotted_string != "2.16.840.1.101.3.4.2.1":
        raise ValueError("Expected a SHA-256 message imprint")
    verifier = (
        tsp.VerifierBuilder().add_root_certificate(root).tsa_certificate(signer)
        .nonce(nonce).build()
    )
    if not verifier.verify_message(response, commitment):
        raise ValueError("Timestamp verification did not succeed")
    return {
        "status": "single_authority_signature_valid", "provider": "freetsa",
        "authority_count": 1, "quorum_met": False,
        "provider_time": response.tst_info.gen_time.isoformat(),
        "provider_policy_oid": response.tst_info.policy.dotted_string,
        "commitment_sha256": hashlib.sha256(commitment).hexdigest(),
        "revocation_checked": False, "timing_accuracy_policy_approved": False,
    }


def request_timestamp(commitment: bytes, client: httpx.Client) -> tuple[bytes, bytes, int]:
    request = tsp.TimestampRequestBuilder().data(commitment).hash_algorithm(tsp.HashAlgorithm.SHA256).build()
    if request.nonce is None:
        raise ValueError("Timestamp request must include a nonce")
    with client.stream("POST", TSA_URL, content=request.as_bytes(), headers={
        "Content-Type": "application/timestamp-query", "Accept": "application/timestamp-reply",
    }) as response:
        response.raise_for_status()
        if response.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/timestamp-reply":
            raise ValueError("Unexpected timestamp response type")
        data = bytearray()
        for chunk in response.iter_bytes():
            if len(data) + len(chunk) > MAX_RESPONSE_BYTES:
                raise ValueError("Timestamp response exceeds size limit")
            data.extend(chunk)
    return request.as_bytes(), bytes(data), request.nonce


def main() -> int:
    parser = argparse.ArgumentParser(description="Single-authority RFC 3161 experiment; not multi-witness confirmation")
    parser.add_argument("command", choices=["stamp", "verify"])
    parser.add_argument("receipt", type=Path)
    parser.add_argument("evidence_directory", type=Path)
    args = parser.parse_args()
    try:
        commitment = batch_commitment(read_bounded(args.receipt, MAX_RECEIPT_BYTES))
        folder = args.evidence_directory
        if args.command == "stamp":
            trusted_certificates()  # Fail before network access if trust files changed.
            folder.mkdir(parents=True, exist_ok=False)  # Never overwrite existing evidence.
            with httpx.Client(timeout=20, trust_env=False, follow_redirects=False) as client:
                query, reply, nonce = request_timestamp(commitment, client)
            # Preserve raw evidence even when validation fails. No success report
            # or registration state is written before cryptographic verification.
            (folder / "commitment.json").write_bytes(commitment)
            (folder / "request.tsq").write_bytes(query)
            (folder / "response.tsr").write_bytes(reply)
            (folder / "request-metadata.json").write_text(json.dumps({"nonce": nonce}), encoding="utf-8")
            result = verify_timestamp(commitment, reply, nonce)
        else:
            if read_bounded(folder / "commitment.json", 4096) != commitment:
                raise ValueError("Evidence does not match the receipt's batch commitment")
            metadata = json.loads(read_bounded(folder / "request-metadata.json", 4096))
            result = verify_timestamp(commitment, read_bounded(folder / "response.tsr", MAX_RESPONSE_BYTES), metadata["nonce"])
        if args.command == "stamp":
            (folder / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, httpx.HTTPError, tsp.VerificationError):
        print("Timestamp experiment failed; no witness quorum is established. Check evidence, trust files, and provider availability.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
