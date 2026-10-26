# rootproof
PostgreSQL-first API for cryptographically verifiable data using Merkle proofs and x402 micropayments.

Current milestone: **M-002 — repository setup**. This repository contains the Python
package and development setup. API and database behavior will follow in later
milestones; see [PROJECT.md](PROJECT.md).

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
Pydantic / pydantic-settings, and pytest. Docker Compose and PostgreSQL setup arrive
in M-003. There is no server command yet.

Keep real configuration in the ignored `.env`; the committed `.env.example` contains
only blank values reserved for M-003. Environment loading is not implemented yet.
Ignore rules protect common local secret files, but do not detect secrets pasted
into source files. Review `git diff --cached` before every commit.

Run tests from the repository root using `python -m pytest` with your virtual
environment's Python. The initial smoke test checks that the package imports.
