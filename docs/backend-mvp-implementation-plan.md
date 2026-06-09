# AS Survey Backend MVP Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a working backend MVP that imports the validated Excel blueprint, stores AS Survey data in SQLite, exposes AS/admin APIs, and can later connect to the existing prototype UI.

**Architecture:** Use a small FastAPI app with SQLite. Keep import, validation, auth, survey progress, AS task submission, and export logic separate so the MVP remains easy to test. Use local file storage for uploaded photos in Phase 1.

**Tech Stack:** Python 3, FastAPI, SQLite, stdlib `sqlite3`, `pytest`, local uploads folder.

---

## Current Context

Existing files:

- Prototype: `/opt/data/as-survey-system/prototype/index.html`
- PRD: `/opt/data/as-survey-system/docs/AS-Survey-Task-System-PRD.md`
- Backend/API spec: `/opt/data/as-survey-system/docs/backend-database-api-spec.md`
- SQL schema: `/opt/data/as-survey-system/backend/schema.sql`
- Validated Excel blueprint: `/opt/data/cache/documents/as_survey_system_fixed.xlsx`

Important requirements:

- AS tasks are grouped by survey.
- Active/Completed surveys are separated in AS UI.
- Submitted tasks remain visible with `View submitted`.
- Admin controls survey deadline.
- AS sees each survey/task deadline clearly.
- Use AS Code + PIN, not AS Code alone.
- Store hashed PIN, never plain PIN.

---

## Task 1: Create Backend Project Skeleton

**Objective:** Create the minimal backend directory structure and app entrypoint.

**Files:**

- Create: `/opt/data/as-survey-system/backend/app/__init__.py`
- Create: `/opt/data/as-survey-system/backend/app/main.py`
- Create: `/opt/data/as-survey-system/backend/app/db.py`
- Create: `/opt/data/as-survey-system/backend/app/security.py`
- Create: `/opt/data/as-survey-system/backend/app/importer.py`
- Create: `/opt/data/as-survey-system/backend/app/routes_auth.py`
- Create: `/opt/data/as-survey-system/backend/app/routes_admin.py`
- Create: `/opt/data/as-survey-system/backend/app/routes_as.py`
- Create: `/opt/data/as-survey-system/backend/app/routes_import.py`
- Create: `/opt/data/as-survey-system/backend/tests/test_schema.py`
- Create: `/opt/data/as-survey-system/backend/requirements.txt`

**Implementation notes:**

`requirements.txt` should include:

```text
fastapi
uvicorn
python-multipart
pytest
```

Avoid `openpyxl` for now unless pip is available. If pip is unavailable on server, use the existing lightweight XLSX parser approach from Genos session.

**Verification:**

Run:

```bash
cd /opt/data/as-survey-system/backend
python3 -m py_compile app/*.py
```

Expected: no syntax errors.

---

## Task 2: Implement SQLite DB Helper

**Objective:** Provide reusable DB connection and schema initialization.

**Files:**

- Modify: `/opt/data/as-survey-system/backend/app/db.py`
- Test: `/opt/data/as-survey-system/backend/tests/test_schema.py`

**Implementation details:**

`db.py` should expose:

```python
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "as_survey.db"
SCHEMA_PATH = ROOT / "schema.sql"


def connect(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path = DB_PATH):
    conn = connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    return conn
```

**Test idea:**

- Create temp SQLite DB.
- Run `init_db(temp_db)`.
- Assert core tables exist: `users`, `branches`, `surveys`, `survey_tasks`, `survey_questions`.

**Verification:**

Run:

```bash
cd /opt/data/as-survey-system/backend
pytest tests/test_schema.py -v
```

Expected: pass.

---

## Task 3: Implement PIN Hashing + Simple Session Token

**Objective:** Support AS/admin login securely enough for MVP.

**Files:**

- Modify: `/opt/data/as-survey-system/backend/app/security.py`
- Create: `/opt/data/as-survey-system/backend/tests/test_security.py`

**Implementation details:**

Use stdlib only:

```python
import base64
import hashlib
import hmac
import os
import secrets


def hash_pin(pin: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 120_000)
    return "pbkdf2_sha256$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_pin(pin: str, stored: str) -> bool:
    alg, salt_b64, digest_b64 = stored.split("$", 2)
    if alg != "pbkdf2_sha256":
        return False
    salt = base64.b64decode(salt_b64)
    expected = base64.b64decode(digest_b64)
    actual = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 120_000)
    return hmac.compare_digest(actual, expected)


def new_token() -> str:
    return secrets.token_urlsafe(32)
```

**Verification:**

- Hash a PIN.
- Verify correct PIN passes.
- Verify wrong PIN fails.

---

## Task 4: Implement Lightweight XLSX Reader

**Objective:** Read the validated Excel blueprint without requiring external packages.

**Files:**

- Modify: `/opt/data/as-survey-system/backend/app/importer.py`
- Create: `/opt/data/as-survey-system/backend/tests/test_xlsx_reader.py`

**Implementation details:**

Port the session's lightweight parser:

- Use `zipfile`
- Parse `xl/workbook.xml`
- Parse `xl/_rels/workbook.xml.rels`
- Support `inlineStr`, shared strings, and plain values
- Return shape:

```python
{
  "AS_USERS": [
    {"as_code": "BKK10", ...}
  ],
  ...
}
```

**Verification:**

Run parser on:

```text
/opt/data/cache/documents/as_survey_system_fixed.xlsx
```

Assert row counts:

- `AS_USERS`: 2
- `BRANCHES`: 16
- `SURVEYS`: 4
- `SURVEY_BRANCHES`: 6
- `QUESTIONS`: 5
- `RESPONSES`: 5
- `RESPONSE_FILES`: 4
- `STATUS_LOG`: 4
- `ADMIN_SETTINGS`: 9

---

## Task 5: Implement Import Validation

**Objective:** Validate references before writing to database.

**Files:**

- Modify: `/opt/data/as-survey-system/backend/app/importer.py`
- Create: `/opt/data/as-survey-system/backend/tests/test_import_validation.py`

**Rules:**

Reject when:

- Duplicate `as_code`
- Duplicate `branch_code`
- Duplicate `survey_id`
- Duplicate `task_id`
- Branch assigned AS missing from `AS_USERS`
- Task branch missing from `BRANCHES`
- Task AS missing from `AS_USERS`
- Question survey missing from `SURVEYS`
- Response task missing from `SURVEY_BRANCHES`
- Response question missing from its survey's questions
- File response missing from `RESPONSES`
- Status log task missing from `SURVEY_BRANCHES`

**Return shape:**

```python
{
  "valid": True,
  "errors": [],
  "counts": {"AS_USERS": 2, ...}
}
```

---

## Task 6: Implement Excel Import into SQLite

**Objective:** Import validated Excel into DB transactionally.

**Files:**

- Modify: `/opt/data/as-survey-system/backend/app/importer.py`
- Create: `/opt/data/as-survey-system/backend/tests/test_import_to_db.py`

**Import order:**

1. `AS_USERS` → `users`
2. seed admin `ADM01` if missing
3. `BRANCHES` → `branches`
4. `SURVEYS` → `surveys`
5. `SURVEY_BRANCHES` → `survey_tasks`
6. `QUESTIONS` → `survey_questions`
7. `RESPONSES` → `survey_responses` + `survey_answers`
8. `RESPONSE_FILES` → `response_files`
9. `STATUS_LOG` → `status_logs`
10. `ADMIN_SETTINGS` → `admin_settings`

**Important mapping:**

- PIN values from Excel must be hashed before insert.
- Normalize roles: `AS` → `as`, `Admin` → `super_admin`.
- Normalize statuses to lowercase.
- Split options by `|` and store JSON array.

**Verification:**

Import fixed workbook into temp DB and assert:

- `SELECT COUNT(*) FROM users` includes 2 AS + seeded admin
- `SELECT COUNT(*) FROM branches` = 16
- `SELECT COUNT(*) FROM survey_tasks` = 6
- `SELECT COUNT(*) FROM survey_questions` = 5
- `SELECT issue_count` equivalent = 0 from validator

---

## Task 7: Implement Auth Routes

**Objective:** AS/admin can login and receive a session token.

**Files:**

- Modify: `/opt/data/as-survey-system/backend/app/routes_auth.py`
- Modify: `/opt/data/as-survey-system/backend/app/main.py`
- Create: `/opt/data/as-survey-system/backend/tests/test_auth_routes.py`

**Endpoints:**

- `POST /api/auth/as-login`
- `POST /api/auth/admin-login`

**MVP session design:**

For development, use an in-memory token store:

```python
SESSIONS = {token: {"user_id": 1, "role": "as"}}
```

Future production should use signed JWT or DB sessions.

**Verification:**

- Correct AS code/PIN returns token.
- Wrong PIN fails.
- Inactive user fails.

---

## Task 8: Implement AS Task APIs

**Objective:** AS users can fetch their grouped survey tasks.

**Files:**

- Modify: `/opt/data/as-survey-system/backend/app/routes_as.py`
- Create: `/opt/data/as-survey-system/backend/tests/test_as_tasks.py`

**Endpoints:**

- `GET /api/as/tasks`
- `GET /api/as/tasks/{task_id}`

**Rules:**

- AS sees only own tasks.
- Group by survey.
- Include deadline at survey and task level.
- Submitted tasks remain visible.

**Verification:**

Use imported workbook:

- Login `BKK10`.
- Call `/api/as/tasks`.
- Assert returned tasks only have assigned AS `BKK10`.
- Assert response contains `deadline`.

---

## Task 9: Implement AS Submit API

**Objective:** AS can submit responses for owned tasks.

**Files:**

- Modify: `/opt/data/as-survey-system/backend/app/routes_as.py`
- Create: `/opt/data/as-survey-system/backend/tests/test_as_submit.py`

**Endpoint:**

- `POST /api/as/tasks/{task_id}/submit`

**Rules:**

- User must own task.
- Required answers must be present.
- Number answers must parse.
- Photo required questions require file record/upload.
- On success, task status becomes `submitted` and `submitted_at` is set.

**MVP simplification:**

For first pass, accept JSON photo links instead of physical upload. Add real multipart upload later.

---

## Task 10: Implement Admin Progress APIs

**Objective:** Admin can see survey progress and pending details.

**Files:**

- Modify: `/opt/data/as-survey-system/backend/app/routes_admin.py`
- Create: `/opt/data/as-survey-system/backend/tests/test_admin_progress.py`

**Endpoints:**

- `GET /api/admin/surveys/progress`
- `GET /api/admin/surveys/{survey_id}/progress`
- `GET /api/admin/surveys/{survey_id}/responses`

**Use views:**

- `survey_progress`
- `survey_progress_by_as`

**Verification:**

- Progress list returns one row per non-deleted survey.
- Completion % = submitted / assigned × 100.
- Pending by AS identifies AS with pending > 0.

---

## Task 11: Implement Admin Import API

**Objective:** Upload fixed Excel file and import into DB.

**Files:**

- Modify: `/opt/data/as-survey-system/backend/app/routes_import.py`
- Modify: `/opt/data/as-survey-system/backend/app/main.py`
- Create: `/opt/data/as-survey-system/backend/tests/test_import_route.py`

**Endpoint:**

- `POST /api/admin/import/excel`

**Rules:**

- Validate first.
- Import inside transaction.
- Return counts and errors.

---

## Task 12: Add Smoke Run Script

**Objective:** Make it easy to start/test backend on VPS.

**Files:**

- Create: `/opt/data/as-survey-system/backend/run.sh`
- Create: `/opt/data/as-survey-system/backend/README.md`

`run.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8030
```

README should include:

```bash
cd /opt/data/as-survey-system/backend
python3 -m pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8030
```

If `pip` is unavailable on VPS, use system package install or create venv after installing pip.

---

## Task 13: Connect Prototype to APIs Incrementally

**Objective:** Replace mock data in prototype with backend API calls.

**Files:**

- Modify: `/opt/data/as-survey-system/prototype/index.html`

**Order:**

1. Add `const API_BASE = 'http://localhost:8030/api';`
2. Replace AS login mock with `/api/auth/as-login`.
3. Replace AS task list with `/api/as/tasks`.
4. Replace admin progress with `/api/admin/surveys/progress`.
5. Replace branch list filters with `/api/branches`.

**Verification:**

- AS login shows tasks from imported Excel.
- Admin progress shows survey rows from DB.
- Deadline remains visible on AS survey cards.

---

## Risks / Tradeoffs

- **No pip installed currently:** If FastAPI cannot be installed immediately, build the first backend with Python stdlib HTTP or install pip/venv. FastAPI remains the recommended target.
- **Excel parser limitations:** The lightweight parser supports normal workbook cells but not every Excel edge case. For production import, use `openpyxl` once environment allows pip.
- **Auth MVP:** In-memory sessions are OK for prototype, but production should use persistent signed sessions/JWT and HTTPS.
- **File uploads:** Start with photo URLs/local file path references; multipart upload and image compression can be Phase 2.
- **Submitted edit behavior:** Default should be locked after submit unless `allow_edit_after_submit` is enabled.

---

## Completion Criteria

Backend MVP is ready when:

- Fixed Excel imports with zero reference errors.
- AS `BKK10` can login with PIN from blueprint.
- AS task list returns grouped surveys with deadlines.
- AS can submit a task and admin progress updates.
- Admin progress returns per-survey, by-AS, pending branches, and responses.
- Existing prototype can read at least AS tasks and admin progress from backend.
