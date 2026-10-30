# rootproof
Register file hashes and selected metadata without uploading original documents.
Portable Merkle receipts and independent witness evidence are planned; x402 agent
payments will follow later.

Completed milestone: **M-004 — FastAPI walking skeleton**. The health endpoint
checks PostgreSQL connectivity. Hash registration and integrity features are not
implemented yet; see [PROJECT.md](PROJECT.md).

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
M-003. No migration revisions exist yet; registration models arrive in M-005.
`alembic upgrade head` checks migration connectivity and may create Alembic's
version table, but creates no registration tables.

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
