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
| M-003 | Local PostgreSQL, SQLAlchemy 2, psycopg 3, Alembic; verify connection | Doing; live database verification pending |
| M-004 | FastAPI app and GET /health verifying database connectivity | Backlog |
| M-005–008 | Hash registrations, selected metadata, local file hashing, versioned commitment encoding | Backlog |
| M-009–012 | Versioned deterministic Merkle trees, batches, proofs, verification, tamper tests | Backlog |
| M-013 | Independent witnessed root commitments; mechanism intentionally undecided | Backlog |
| M-014–015 | Selected-folder registration tool and customer pilot | Backlog |

M-003 is the current task. Docker is optional: use local PostgreSQL and a Python
virtual environment. M-004 and later features are outside this milestone.

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
