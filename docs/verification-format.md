# Registration format version 1

## File digest

Calculate SHA-256 over the exact bytes of the file, with no newline conversion,
text decoding, document parsing, or normalization. Represent the result as 64
lowercase hexadecimal characters. File names are not part of the file digest.

The local tool reads in 64 KiB chunks. It checks size and modification/change
times before and after reading and rejects detected changes. These checks are
best effort, not a filesystem snapshot or a defense against malicious concurrent
modification. Hash saved, stable files.

## Protected registration

Encode exactly these fields using [RFC 8785 JCS](https://www.rfc-editor.org/rfc/rfc8785):

| Field | Version 1 representation |
| --- | --- |
| type | Literal string `rootproof.registration` |
| format_version | Integer `1` |
| id | Lowercase hyphenated UUID string |
| digest | Lowercase SHA-256 hex digest |
| hash_algorithm | Literal string `sha256` |
| received_at | UTC timestamp with exactly six fractional digits and suffix `Z` |
| registration_metadata | JSON object |

The output is UTF-8 canonical JSON bytes, without a BOM or trailing newline.
Normalize an aware timestamp to UTC before encoding; reject timezone-less values.
Do not use a client event time as the server receipt time.

Use JSON strings, objects with string keys, arrays, booleans, null, and finite
numbers. Integers and floats must have absolute value at most 9007199254740991.
Represent larger values and precision-sensitive scientific measurements as strings.
Strings must contain valid Unicode and no NUL characters, including object keys.
Metadata nesting is limited to 32 levels below the root object.
Unicode is preserved without normalization. This subset supports PostgreSQL JSONB
round trips. Metadata size enforcement remains the registration schema's 8192-byte
limit on PostgreSQL's JSONB text representation; the encoder does not replace that
database check. Submission validation enforces the encoding rules and rejects
duplicate JSON keys instead of silently choosing one value.

An exact encoding test vector is in `tests/test_integrity.py`. Equivalent object
key ordering and timezone offsets produce identical bytes. Changes to the digest,
identifier, receipt time, or metadata change the encoded bytes.

The implementation uses the [rfc8785 package](https://github.com/trailofbits/rfc8785.py).
It has no dependency on the API, PostgreSQL, or local credentials.

This encoding is not a Merkle proof or witness receipt. The implemented leaf and
node hashing rules are documented in [merkle-format.md](merkle-format.md).
Persisted batch positions and proof formats follow in M-010 through M-012.
External witness evidence arrives in M-013. No independent timing claim exists yet.
