# rootproof
Register file hashes and selected metadata without uploading original documents.
Portable Merkle receipts and independent witness evidence are planned; x402 agent
payments will follow later.

Completed milestone: **M-012 — offline file-and-receipt verification**.
The API stores hash registrations, seals batches, and exports inclusion receipts.
Offline verification works; external witnessing is next. See [PROJECT.md](PROJECT.md).

M-013 is in progress: a separate RFC 3161 single-authority experiment has passed
against FreeTSA using synthetic public test data. It is not a production timestamp
or multi-witness integration. See [the decision and prototype](docs/timestamping-decision.md).

## Local document interface preview

With the API running in a separate terminal, start Document Desk from the
repository root:

```powershell
.\.venv\Scripts\python.exe -m clients.desktop
```

Choose an individual file to hash locally, optionally include its file name, and
register its fingerprint. The client re-hashes before submission to reject changes
since the preview. File contents and full local paths are not uploaded. This
preview connects only to http://127.0.0.1:8000 and does not access database credentials.

Paste an existing registration ID or use the returned ID to refresh its status.
Save registration details while pending; these are not inclusion proofs. Once the
operator seals a batch, refresh and save an inclusion receipt. Batch sealing
remains the separate `python -m app.db.batch` operator command.

The second tab checks a file and saved inclusion receipt offline. It displays
file and proof matches separately and explicitly says independent timestamp
evidence is not verified. The separate FreeTSA experiment is not integrated into
this interface or the receipt; no external timestamp requests occur from the GUI.

This is an individual-file preview, not a folder scanner or a backup service.
Tkinter must be available in the Python installation (included with standard
Windows Python installers; Linux may require its distribution's Tk package).
Selecting, hashing, and registration were tested in the Windows UI. Receipt and
verification operations have automated workflow coverage; their remaining manual
UI checks were interrupted and are not represented as complete.

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

## Export an inclusion receipt

Restart Uvicorn after updating the code. For a registration that has been sealed,
open `/registrations/YOUR_REGISTRATION_ID/receipt` or download it from PowerShell:

```powershell
New-Item -ItemType Directory -Force '.local\receipts' | Out-Null
Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/registrations/YOUR_REGISTRATION_ID/receipt' -OutFile '.local\receipts\receipt.json'
```

Replace YOUR_REGISTRATION_ID with the actual UUID. The response contains the
protected registration, batch root and size, position, sibling hashes, and version
identifiers. It explicitly reports sealed_pending_witnesses. It is not a trusted
timestamp or externally witnessed receipt. Unbatched registrations return 409.

Receipt export does not require a database migration. The .local directory is
ignored by Git; exported receipts can contain private metadata. See
[the receipt format](docs/receipt-format.md) for details and trust boundaries.
The offline verifier is available below; clients compare remains database-only.

## Verify a receipt offline

```powershell
.\.venv\Scripts\python.exe -m clients verify "C:\path\to\file.txt" ".local\receipts\receipt.json"
```

The command hashes the exact file bytes and checks the protected registration and
inclusion path against the root in the receipt. It does not load database settings
or make network requests. The API and PostgreSQL can be unavailable.

A passing result has status `valid_unwitnessed`, file_matches and inclusion_valid
both true, basis `supplied_receipt_root`, and witness_status `not_verified`.
This proves consistency with the supplied root, not its historical publication or
an independently trustworthy timestamp. Replacing an entire receipt consistently
is still possible without external witness evidence.

Exit codes: 0 for valid unwitnessed consistency, 1 for a file/proof mismatch, and
2 for malformed input or processing errors. See the receipt format for strict
validation rules and trust boundaries. No database migration or server restart is
needed to use the offline command.

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
