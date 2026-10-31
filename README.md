# rootproof
Register file hashes and selected metadata without uploading original documents.
Portable Merkle receipts and independent witness evidence are planned; x402 agent
payments will follow later.

Completed milestone: **M-010 — persisted Merkle batches**.
The API stores and retrieves hash registrations and reports batch membership.
Inclusion proofs and witnessing are not implemented yet; see [PROJECT.md](PROJECT.md).

## Development setup

Install Python **3.12 or newer** and Git. From the repository root, create a virtual
environment and install the initial stack:

```powershell
# Windows PowerShell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pytest
```

```sh
# Linux / macOS (python3 must be 3.12+)
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m pytest
```

Virtual environment activation is optional; these commands use its interpreter
directly. Dependencies have major-version bounds; this is an initial development
baseline, not a locked production environment.

The stack is FastAPI, Uvicorn, PostgreSQL, SQLAlchemy 2, psycopg 3, Alembic,
Pydantic / pydantic-settings, and pytest. Install PostgreSQL locally; Docker is
optional.

Keep real configuration in the ignored `.env`; the committed `.env.example` contains
the blank DATABASE_URL and its format. Environment variables override .env values.
Ignore rules protect common local secret files, but do not detect secrets pasted
into source files. Review `git diff --cached` before every commit.

Run tests from the repository root using `python -m pytest` with your virtual
environment's Python. The initial smoke test checks that the package imports.

## Local PostgreSQL setup

Install PostgreSQL using the installer linked at
https://www.postgresql.org/download/windows/ or your Linux package manager.
Keep the database local. Keep the administrator password private.

Connect as the administrator through SQL Shell (psql), then run:

```sql
CREATE ROLE rootproof_dev LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
\password rootproof_dev
CREATE DATABASE rootproof_dev OWNER rootproof_dev;
```

The password command prompts privately. This dedicated development role owns its
database for migrations. Production will separate migration and application access.
Fill DATABASE_URL in your local .env using the format in .env.example. URL-encode
special characters in the password. Do not use the administrator account.

```powershell
.\.venv\Scripts\python.exe -m app.db.check
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head
$env:ROOTPROOF_TEST_DATABASE = "1"
.\.venv\Scripts\python.exe -m pytest
Remove-Item Env:ROOTPROOF_TEST_DATABASE
```

On Linux use `.venv/bin/python`; opt in to the live test with
`ROOTPROOF_TEST_DATABASE=1 .venv/bin/python -m pytest`.

Without that opt-in the live test is skipped. Unit tests alone do not complete
M-003. `alembic upgrade head` creates Alembic's version table and applies the
registration schema migration. Database tests use temporary schemas inside
rolled-back transactions; they do not erase development registrations.

The registration table stores a UUID, a lowercase 64-character SHA-256 digest,
algorithm, selected JSONB metadata, database receipt time, and format version.
Metadata must be a JSON object whose PostgreSQL text representation is at most
8192 bytes. Do not use metadata to upload documents or confidential file contents.
The database records a receipt time, not an independently witnessed timestamp.
Local file hashing and versioned commitment encoding are implemented. Registration
submission is available through POST /registrations; retrieve by ID using
GET /registrations/{id}.

## Hash a file locally

```powershell
.\.venv\Scripts\python.exe -m clients hash "C:\path\to\document.pdf"
```

This prints JSON containing the algorithm and digest. It does not read .env,
connect to the API, upload a file, or store a registration. It works without a
running server. Quote paths containing spaces. Missing files or detected changes
during reading produce an error and nonzero exit status.

Identical file bytes produce the same digest even after renaming. Re-saving a
document may change its bytes even if it looks identical. See
[the versioned encoding specification](docs/verification-format.md) for the
separate format that will protect registration metadata in Merkle batches.

## Register a hash

Restart the local server after code changes (Ctrl+C, then the Uvicorn command
above). In a second PowerShell window at the repository root:

```powershell
$digest = (Get-FileHash -LiteralPath README.md -Algorithm SHA256).Hash.ToLowerInvariant()
$body = @{
    digest = $digest
    hash_algorithm = 'sha256'
    registration_metadata = @{ document_name = 'README.md' }
} | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/registrations' -Method Post -ContentType 'application/json' -Body $body
```

The API returns HTTP 201 with the database-generated id, digest, metadata,
server receipt time, format version, and status `pending_batch`. This is a saved
registration, not a Merkle proof or independently witnessed receipt. Keep the
returned id. Repeating the request creates another registration; retries are not
idempotent yet.

Only application/json is accepted, with a 32768-byte body limit. Unknown fields,
client-assigned receipt times, unsupported algorithms, invalid digests, duplicate
JSON keys, and nonportable metadata are rejected. Metadata must also fit the
database's 8192-byte JSONB text limit. Invalid inputs return 422; oversized bodies
return 413, unsupported media types 415, and database failures 503 without exposing
connection details. Selected metadata is echoed in the registration response.

This prototype has no authentication. Keep it bound to 127.0.0.1 for local
development and use non-sensitive sample metadata. Multi-user or public deployment
requires authentication and authorization first. There is no document upload route.

## Compare a file with a saved registration

Restart the server after code changes. Substitute the ID returned when you
registered the file:

```powershell
.\.venv\Scripts\python.exe -m clients compare "C:\path\to\file.txt" YOUR_REGISTRATION_ID
```

The command hashes the file locally and makes a GET request for the registration;
it sends no file contents or locally calculated digest. It reports `match` or
`mismatch` with basis `database_registration_only`. This trusts the API/database
registration; it is not independent Merkle or witnessed verification.

Exit codes: 0 for a match, 1 for a mismatch, 2 for an error such as a missing file,
unknown registration, unavailable API, or malformed response. The API defaults to
http://127.0.0.1:8000; override with `--api-url` when needed.

GET /registrations/{id} returns the registration with HTTP 200, or 404 for an
unknown UUID, 422 for an invalid UUID, and 503 for database failures. It has no
ownership checks yet, so the local-only development restriction still applies.

Use a stable sample file for demonstrations. README.md changes as we document
milestones, so its current hash may differ from one registered earlier. A mismatch
in that situation is expected. Preserve the original file if you want to compare
it later; Rootproof does not store or restore its contents.

## Merkle construction

The shared `integrity.merkle` module calculates roots from ordered byte entries
using the SHA-256 tree construction in RFC 9162. Application entries are complete
canonical registration encodings, so metadata and receipt times are protected
alongside file digests. See [the versioned tree specification](docs/merkle-format.md).

## Seal a batch locally

Apply the database migration before running updated API code, then restart Uvicorn:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.db.batch --limit 1000
```

The operator command seals up to 1000 pending registrations in one transaction.
It returns the batch ID, root, size, construction version, sealed time, and status
`sealed_pending_witnesses`. With no pending registrations it reports
`no_pending_registrations` without creating an empty batch.

GET /registrations/{id} now includes batch_id and batch_position (null before
sealing), and reports sealed_pending_witnesses after inclusion. File comparison
still checks only the stored digest; it does not verify batch inclusion yet.

The batch root is reproducible from saved canonical entries in position order.
Database constraints and triggers prevent ordinary changes to sealed data.
Privileged database administrators can bypass those controls; independent
witnessing has not been implemented. See the tree specification for trust limits
and transaction behavior. Never run migration downgrades on evidence-bearing data
as routine maintenance: they intentionally remove batch data and protections.

## Start the local API

From the repository root, with DATABASE_URL configured in .env:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On Linux use `.venv/bin/python` with the same arguments. Keep the terminal open;
press Ctrl+C to stop the server.

Open http://127.0.0.1:8000/health. A reachable database produces HTTP 200 with
`{"status":"ok","database":"ok"}`. A failed database check produces HTTP 503
with `{"status":"unhealthy","database":"unavailable"}`. Missing or invalid
configuration prevents startup. Interactive API documentation is at
http://127.0.0.1:8000/docs. This command listens only on your local computer.
