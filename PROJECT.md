# Rootproof project

Rootproof is a PostgreSQL-first API for cryptographically verifiable data.
The eventual MVP lets an independent buyer pay through x402, receive a record
and Merkle proof, verify against an externally committed root, and detect tampering.

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
| M-002 | Package, dependencies, configuration example, testing, documentation | Testing / awaiting review |
| M-003 | PostgreSQL in Docker Compose, SQLAlchemy 2, psycopg 3, Alembic; verify connection | Backlog |
| M-004 | FastAPI app and GET /health verifying database connectivity | Backlog |
| M-005–008 | Records, JSONB payloads, versioned canonicalization, SHA-256, record endpoints | Backlog |
| M-009–012 | Versioned deterministic Merkle trees, batches, proofs, verification, tamper tests | Backlog |
| M-013 | External root commitment; mechanism intentionally undecided | Backlog |
| M-014–017 | x402, payment verification and records, paid data and proof delivery | Backlog |

M-003 begins only after M-002 has been reviewed and accepted.
No application server, database connection, or future feature is implemented in M-002.

## Integrity and completion

Use established cryptographic primitives. Canonicalization and tree construction
must eventually have explicit, versioned rules. Keep credentials out of Git and
use environment variables for configuration. Database permissions should eventually
follow least privilege. Production deployment is outside the current milestone.

A task is done when relevant and existing automated tests pass, documentation is
current, no secrets are committed, and changes are understandable and ready to commit.
