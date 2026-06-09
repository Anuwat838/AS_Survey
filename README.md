# AS Survey System

Backend-connected MVP for AS branch surveys.

## Features

- AS login and task list
- AS survey submission with photo upload support
- Admin progress dashboard
- Admin create survey flow: draft, branch selection, question builder, publish
- Admin user management: create/edit users and reset PINs
- Admin branch list CSV import for the branch picker used while creating surveys

## Local run

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8030
```

Open the prototype:

```text
prototype/index.html
```

Default dev API base:

```text
http://127.0.0.1:8030/api
```

## Runtime files not committed

The repository intentionally ignores live/private runtime data:

- SQLite databases: `*.db`, `*.db-*`, `*.sqlite*`
- Uploaded photos: `backend/uploads/`
- Backups: `backups/`
- Virtual environments and test caches
- `.env` files

Before production use, initialize/import branch/user data on the server and change all seed PINs.

## Branch CSV import format

Required columns:

```csv
branch_code,branch_name,account,region,province,assigned_as_code,status,note
```

Notes:

- `assigned_as_code` must already exist as an AS user.
- Existing `branch_code` rows are updated.
- New `branch_code` rows are inserted.
- `status` supports `active` or `inactive`.
