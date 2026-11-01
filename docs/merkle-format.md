# Merkle construction version 1

Construction identifier: `rootproof.merkle.rfc9162.sha256.v1`.

Rootproof uses SHA-256 with the Merkle tree hash definition from
[RFC 9162 section 2.1](https://www.rfc-editor.org/rfc/rfc9162.html#section-2.1).
This adopts the tree algorithm, not the complete Certificate Transparency protocol.

## Entries and order

Each entry is the complete version 1 canonical registration encoding defined in
[verification-format.md](verification-format.md). It protects the registration
identifier, file digest, algorithm, metadata, server receipt time, and format version.
It is not merely the file's digest, its hex text, or a prehashed leaf.

Input order is significant. The root calculator preserves the caller's order and
does not sort or deduplicate entries. Sets and mappings are rejected as containers.
An ordered generator is supported. The caller must supply a stable order.

M-010 selects unassigned registrations ordered by server receipt time and then
UUID, assigns zero-based positions, and persists both positions and exact encoded
entry bytes. Reproduction uses persisted positions, never unspecified query order.
UUID ordering breaks receipt-time ties; it does not claim chronological ordering
between simultaneous submissions. A registration belongs to at most one batch.

## Hashing rules

All intermediate hashes are 32 raw bytes. Concatenation uses raw bytes, not hex.

- Empty list: `SHA256(b"")`.
- One entry: `SHA256(b"\x00" + entry)`.
- Internal node: `SHA256(b"\x01" + left_hash + right_hash)`.

For a list of n entries where n is greater than one, split at the largest power
of two strictly less than n. Recursively hash the left and right sublists, then
combine them as an internal node. This fixes the shape for every list length.
Do not pad the list or duplicate an odd final entry.

An empty tree is mathematically defined, but sealed database batches must contain
between 1 and 1000 entries. Repeated file digests may appear in different
registrations with different identifiers. Duplicate raw entries contribute
separate leaf positions in the generic root calculator.

The implementation uses the equivalent stack algorithm in RFC 9162 section 2.1.2,
with linear hashing work and logarithmic retained state. Represent a root as 64
lowercase hexadecimal characters when displaying or serializing it. Persist the
construction identifier and tree size alongside roots when batching is implemented.

## Test vectors

`tests/test_merkle.py` contains fixed roots for sizes zero through eight, where
entry i is the single byte i. They were independently computed using Node.js
crypto and the recursive definition. Tests also compare the Python stack algorithm
with a separate recursive reference, including odd counts and power-of-two boundaries.

Example: entries `00`, `01`, `02` give root
`3b6cccd7e3e023ff393006f030315ee7ad9eb111b022b41fba7e5b7a3973f688`.
These are raw byte entries for algorithm tests, not valid application registrations.

## Sealing transaction and database protection

The local operator command `python -m app.db.batch --limit 1000` seals pending
registrations. It is not exposed as an unauthenticated HTTP operation. A PostgreSQL
transaction advisory lock serializes sealers. Selected registration rows are locked
while encoding, and the batch and all entries commit together. Failed transactions
leave registrations unassigned. Registrations arriving after selection wait for a
later batch. Repeating the command seals remaining pending records or reports none.
For an explicit single-registration operation, use
`python -m app.db.batch --registration-id UUID`. This selects only that pending
registration and leaves all other registrations unassigned. It creates no batch
when that registration is missing or already sealed.

PostgreSQL stores batch UUID, root, construction identifier, tree size, sealed time,
and ordered entries with registration IDs and canonical byte snapshots. A deferred
constraint trigger requires all declared entries at commit. Unique positions and
position bounds prevent later additions to a complete batch. Mutation triggers
block updates/deletes of batch and entry rows and batched registrations; truncate
is also blocked. The server receipt time and sealed time are database times only.

The Python service computes the root; database triggers do not implement Merkle
algorithms or validate cryptographic correspondence for arbitrary hand-written SQL.
An owner or administrator can disable triggers or change the schema. These guards
prevent ordinary mutations, not privileged history rewriting. External independent
witnessing remains required. Migration downgrades intentionally remove protections
and batch data, and must not be used as routine operations on evidence-bearing data.

Retrieval reports `sealed_pending_witnesses` plus batch ID and position after sealing.
Inclusion-proof receipts are available through the M-011 export endpoint. There
are no witness attestations yet.

See [receipt-format.md](receipt-format.md) for the inclusion path and receipt
format implemented in M-011. Offline verification follows in M-012 and external
witnessing follows in M-013.
A root calculated locally is not evidence of external observation or a trusted time.
