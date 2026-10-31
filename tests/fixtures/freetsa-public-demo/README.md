# Public synthetic timestamp fixture

This fixture contains no real user registrations, documents, or metadata.
The input is the fixed public text in ../timestamp-demo.txt and a synthetic
receipt in ../timestamp-demo-receipt.json. Its identifiers and receipt times are
invented test values and must not be interpreted as historical observations.

A single RFC 3161 request was sent to https://freetsa.org/tsr on October 31, 2026.
The resulting signed token reports provider time 2026-10-31T21:18:41Z and policy
OID 1.2.3.4.1. These are the authority's assertions, not an approved accuracy claim.

Files retained:

- commitment.json: canonical batch context, hashed before transmission.
- request.tsq: original DER timestamp request with nonce.
- response.tsr: actual signed DER response.
- request-metadata.json: saved nonce used for verification.

Only the SHA-256 imprint and protocol request fields were transmitted. The source
text, synthetic receipt, and commitment JSON were not uploaded.

Tests verify the actual response under separately configured public certificates
in trust/freetsa. Tests do not contact the service. Revocation checks and timing
policy approval are not implemented; this fixture is not production trust evidence.
