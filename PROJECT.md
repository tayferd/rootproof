# Rootproof project

Rootproof registers locally calculated SHA-256 hashes and selected metadata.
Original documents remain with the customer. The core MVP will issue portable
receipts linking registrations to Merkle batches and independent witness evidence.
A match establishes correspondence with committed bytes, not ownership or accuracy.

## Development approach

Use Backlog → Ready → Doing → Testing → Done, with at most two active tasks.
Build small, tested vertical slices. Keep Python readable and typed. Use PostgreSQL
for persistence and transactional state; Python handles canonicalization, Merkle
algorithms, HTTP behavior, and external protocols. Avoid extra infrastructure and
abstractions until a demonstrated requirement calls for them.

## Milestones

| Milestone | Scope | Status |
| --- | --- | --- |
| M-001 | Project definition and architecture | Done |
| M-002 | Package, dependencies, configuration example, testing, documentation | Implemented and published |
| M-003 | Local PostgreSQL, SQLAlchemy 2, psycopg 3, Alembic; verify connection | Done |
| M-004 | FastAPI app and GET /health verifying database connectivity | Done |
| M-005 | Registration model and migration with database constraints | Done |
| M-006 | Local file hashing and versioned commitment encoding | Done |
| M-007 | Registration submission with validation and pending status | Done |
| M-008 | Registration retrieval and local file comparison | Done |
| M-009–012 | Versioned deterministic Merkle trees, batches, proofs, verification, tamper tests | Backlog |
| M-013 | Independent witnessed root commitments; mechanism intentionally undecided | Backlog |
| M-014–015 | Selected-folder registration tool and customer pilot | Backlog |

M-003 is complete: the connection check, Alembic current and upgrade head, and all
seven tests passed against local PostgreSQL 18.6. The live test was explicitly
enabled. Local credentials remain in the ignored .env file.
Docker is optional: use local PostgreSQL and a Python virtual environment.
M-004 is complete: GET /health returns 200 for a reachable database and 503 for
database failures without exposing connection details. Ten tests passed, including
the HTTP health check against live PostgreSQL. The database engine is created at
application startup and disposed at shutdown.

M-005 adds the registrations table: database-generated UUID, lowercase SHA-256
hex digest, algorithm, JSONB metadata object limited to 8192 bytes in PostgreSQL's
text representation, timezone-aware server receipt time, and format version 1.
Repeated digests are allowed as separate registrations. Original files are not
stored. Twenty tests pass, including isolated migration upgrade/downgrade tests,
model/schema consistency, and invalid registration rejection.
M-006 adds an offline file hashing CLI and registration encoding using RFC 8785
canonical JSON, documented in docs/verification-format.md. Forty-two tests pass,
including known SHA-256 digests, chunked reads, detected file changes, an exact
encoding vector, equivalent timezone/key ordering, and malformed input rejection.
M-007 adds POST /registrations: bounded JSON requests, portable metadata validation,
transactional persistence, server-generated identity and receipt time, and explicit
pending_batch status. It rejects duplicate keys and file upload requests. Database
failures return generic errors. Tests cover actual persistence and encoding after
JSONB storage, repeated registrations, invalid requests, and metadata-size rollback.
All 61 tests pass with live database integration enabled.
M-008 adds GET /registrations/{id} and a local compare command. It distinguishes
matches, mismatches, and errors without uploading file contents. The comparison
trusts the database registration; no Merkle batches or witnessed receipts exist yet.
Tests cover retrieval, missing/invalid identifiers, database failures, malformed
responses, and a full local file registration-to-comparison flow against PostgreSQL.
All 76 tests pass with live integration enabled.
Keep this unauthenticated prototype local; multi-user exposure requires access
control. M-009 deterministic Merkle construction is next.

## Integrity and completion

Use established cryptographic primitives. Canonicalization and tree construction
must eventually have explicit, versioned rules. Keep credentials out of Git and
use environment variables for configuration. Database permissions should eventually
follow least privilege. Production deployment is outside the current milestone.

A task is done when relevant and existing automated tests pass, documentation is
current, no secrets are committed, and changes are understandable and committed.
Report local commits and confirmed GitHub publication separately.

## Witness model and later integrations

Multiple independent witnesses will attest to batch roots and observation times.
Define the protocol, identities, independence, timing uncertainty, trust policy,
confirmation threshold, and failure handling before M-013 implementation.
Several machines under one operator do not automatically provide independent trust.
Witnessing a root does not validate an earlier timestamp encoded in a registration.
Missing or insufficient evidence must not produce successful witnessed verification.

Private metadata requires access control before multi-user exposure. Independent
verification must work with exported evidence without querying the Rootproof API.
Collection tools and scientific integrations use the same backend. Sensor accuracy,
source identity, and missing measurements require additional controls.

x402 is planned for agents making occasional paid integrity requests, outside the
core MVP. Original experiment data remains stored elsewhere. Later deployment will
use AWS EC2 Linux, systemd, Uvicorn, Nginx, and HTTPS; tmux is for interactive work.
