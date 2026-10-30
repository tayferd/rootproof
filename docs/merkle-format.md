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

M-010 will define how selected registrations receive and persist their batch
positions. Reproduction must use those exact positions, never unspecified database
query order. No automatic batching or database selection is implemented in M-009.

## Hashing rules

All intermediate hashes are 32 raw bytes. Concatenation uses raw bytes, not hex.

- Empty list: `SHA256(b"")`.
- One entry: `SHA256(b"\x00" + entry)`.
- Internal node: `SHA256(b"\x01" + left_hash + right_hash)`.

For a list of n entries where n is greater than one, split at the largest power
of two strictly less than n. Recursively hash the left and right sublists, then
combine them as an internal node. This fixes the shape for every list length.
Do not pad the list or duplicate an odd final entry.

An empty tree is mathematically defined, but this does not mean M-010 will allow
empty sealed batches. Duplicate entries contribute separate leaf positions.

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

M-009 calculates roots only. Inclusion proof generation, receipt formats, and
verification will follow in M-011 and M-012. External witnessing follows in M-013.
A root calculated locally is not evidence of external observation or a trusted time.
