# Inclusion receipt version 1

Identifier: `rootproof.receipt.v1`.

GET `/registrations/{id}/receipt` returns a downloadable JSON document for a
registration in a sealed batch. It returns 409 if the registration is awaiting
batching, 404 if the identifier is unknown, 422 for an invalid identifier, and 503
if evidence is inconsistent or the database is unavailable. It never creates a
batch as a side effect of downloading.

## Fields

| Field | Meaning |
| --- | --- |
| receipt_version | `rootproof.receipt.v1` |
| registration | The protected registration object from registration format version 1 |
| batch.id | Local batch identifier |
| batch.root | 64 lowercase hexadecimal characters representing the Merkle root |
| batch.tree_size | Number of entries, from 1 through 1000 |
| batch.merkle_version | `rootproof.merkle.rfc9162.sha256.v1` |
| batch.sealed_at | Database-recorded batch creation time |
| inclusion_proof.version | `rootproof.inclusion.rfc9162.sha256.v1` |
| inclusion_proof.leaf_index | Zero-based position of this registration |
| inclusion_proof.audit_path | Sibling node hashes, each 64 lowercase hex characters, from the leaf toward the root |
| status | `sealed_pending_witnesses`; no independent witness evidence is present |

The registration object contains exactly the fields in
[verification-format.md](verification-format.md), including its type marker.
Timestamp strings may use an equivalent timezone representation; reconstruct
canonical registration bytes using the versioned UTC encoding rules.

## Inclusion path

Use the [RFC 9162 section 2.1.3 path definition](https://www.rfc-editor.org/rfc/rfc9162.html#section-2.1.3)
with the [version 1 tree construction](merkle-format.md). Decode sibling hashes
from hex into 32-byte values before hashing. Left/right placement is determined
by leaf index and tree size; no direction flags are transmitted. A singleton tree
has an empty path. An odd-sized tree is not padded or duplicated.

The receipt exposes only the target registration and necessary sibling hashes.
It does not include other registrations, original files, or source credentials.
Selected metadata in the target registration remains visible to receipt holders.

## Evidence boundaries

The registration object is protected by the inclusion path. A valid path links it
to the supplied root; it does not independently establish that root's history.
The batch identifier, sealed time, and status are descriptive receipt fields and
are not themselves protected by this registration's Merkle inclusion proof.
Tree size is necessary to interpret the path, but the supplied value and root still
need independent authentication in the eventual witness protocol.

The service checks the stored registration against its sealed byte snapshot,
checks contiguous positions and count, and recalculates the stored root before
issuing a receipt. A privileged attacker who rewrites the entire database can
still produce a new consistent receipt. External witnessing remains M-013.

M-011 exports proofs; M-012 adds offline verification:

```powershell
.\.venv\Scripts\python.exe -m clients verify "C:\path\to\file" "C:\path\to\receipt.json"
```

This command reads only the local file and receipt. It does not load .env, access
PostgreSQL, or contact an API or witness. It recalculates the file digest,
reconstructs the canonical registration, and verifies the RFC inclusion path using
the supplied index, size, and root. Tests include independently computed fixed
vectors as well as real API receipt exports.

Supported receipts must contain exactly the documented version 1 fields. Reject
duplicate JSON keys, unknown fields/versions, nonfinite metadata numbers, invalid
digests and timestamps, and boolean/coerced indexes or sizes. Timestamp inputs may
have up to six fractional digits; greater precision is rejected rather than
silently truncated. Receipt input is limited to 65536 bytes. No trailing proof
nodes or truncated paths are accepted as valid inclusion evidence.

Output separately reports `file_matches`, `inclusion_valid`, and `witness_status`.
Success is labelled `valid_unwitnessed` with basis `supplied_receipt_root` and
witness_status `not_verified`. File or proof mismatches produce `failed`.
Malformed/unsupported input is an error, not a valid or witnessed result.

Exit codes: 0 for valid unwitnessed consistency, 1 for failed file/proof checks,
and 2 for errors such as unreadable files or malformed receipts. A zero exit code
does not establish independent root publication, receipt time, or witness agreement.
An attacker replacing the registration, path, and root consistently can still
produce a valid_unwitnessed result. M-013 must authenticate the root and associated
witness policy/time evidence separately. Batch IDs and sealed times remain
descriptive even after an otherwise valid inclusion check.

The `clients compare` command remains a separate database-registration comparison.

No database migration is needed for M-011 or M-012. Local exported examples belong in the
ignored `.local/receipts/` directory, outside Git. Preserve receipts alongside the
corresponding original file in your own storage; neither is recoverable from a hash.
