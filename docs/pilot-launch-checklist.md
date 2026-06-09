# AS Survey Pilot Launch Checklist — ~60 Users

Goal: launch the AS Survey MVP safely for a controlled pilot of around 60 AS/field users.

## Current pilot constraints

- Backend: FastAPI + SQLite on port 8030.
- Prototype frontend: static HTML on port 8021.
- Uploads: local folder `backend/uploads/`.
- Database: SQLite with WAL/busy-timeout tuning.
- This is acceptable for a controlled pilot, not final production architecture.

## Step 1 — Security launch lock

Before sending any link to AS users:

- [ ] Admin PIN is no longer the seed value.
- [ ] `GET /api/admin/security/status` returns `launch_locked: false`.
- [ ] Admin can login with the new PIN.
- [ ] Do not share the admin PIN in chat/docs.

Verification from server:

```bash
cd /opt/data/as-survey-system/backend
python3 - <<'PY'
from app import db
from app.security import verify_pin
conn = db.connect(db.DB_PATH)
row = conn.execute("SELECT pin_hash FROM users WHERE login_code='ADM01' AND role='super_admin' AND status='active'").fetchone()
print({'admin_exists': bool(row), 'default_pin': verify_pin('0000', row['pin_hash']) if row else None})
PY
```

Expected:

```text
{'admin_exists': True, 'default_pin': False}
```

## Step 2 — Prepare real workbook

- [ ] AS user sheet has around 60 active users.
- [ ] Every AS has a non-empty PIN.
- [ ] Every AS code is unique.
- [ ] Every branch code is unique.
- [ ] Every branch has an assigned AS code.
- [ ] Every assigned AS code exists in AS users.
- [ ] Every survey has a deadline.
- [ ] Every survey task references an existing survey, branch, and AS.
- [ ] Every question has an answer type.
- [ ] Photo-required questions are intentional.

## Step 3 — Dry-run import

Do this before writing production/pilot data:

```text
POST /api/admin/import/excel?dry_run=true
```

Expected:

```text
valid: true
error_count: 0
```

If `valid: false`, fix the workbook first. Do not import real data until all validation errors are resolved.

## Step 4 — Backup before import

Run manual backup before a big import or launch window:

```bash
cd /opt/data/as-survey-system
python3 scripts/as_survey_backup.py
```

Check that the backup folder contains:

- `as_survey.db`
- `uploads/`
- `manifest.json`

## Step 5 — Real import

Only after dry-run passes:

```text
POST /api/admin/import/excel
```

The backend also creates a pre-import backup automatically.

## Step 6 — Smoke test pilot users

Prepare a local CSV only on the server, never in chat:

```csv
login_code,pin
BKK10,******
BKK11,******
```

Run:

```bash
cd /opt/data/as-survey-system
python3 scripts/pilot_smoke_test.py --base-url http://127.0.0.1:8030 --users-csv /path/to/users.csv
```

Expected:

- health check passes
- all listed AS users can login
- `/api/as/tasks` returns successfully for each user
- output has no PIN values

## Step 7 — Admin Progress sanity check

In browser:

```text
Admin Login → Admin Progress
```

Check:

- [ ] survey count is correct
- [ ] assigned branch count is correct
- [ ] pending count is correct before launch
- [ ] Review button opens status-only review
- [ ] Admin review does not show raw answers or photo thumbnails

## Step 8 — AS mobile sanity check

For 2–3 pilot AS accounts:

- [ ] Login works on phone browser
- [ ] Task list shows correct branches
- [ ] Deadline is visible
- [ ] Answer form opens
- [ ] Photo upload works
- [ ] Submit works
- [ ] Submitted task remains visible with `View submitted`

## Step 9 — Message to AS users

Send each AS only their own:

- link
- login code
- PIN
- deadline
- short instruction for upload photos
- support contact

Template:

```text
สวัสดีครับ ทีม AS
รบกวนเข้าระบบ Survey ที่ลิงก์: [LINK]
Login code: [AS_CODE]
PIN: [PIN]
กำหนดส่ง: [DATE]

วิธีทำ:
1) Login
2) เลือกสาขาที่ได้รับมอบหมาย
3) กรอกคำตอบและแนบรูปตามข้อที่ระบบแจ้ง
4) กด Submit
5) หลังส่งแล้วจะเห็น View submitted เพื่อเช็คงานที่ส่งแล้ว

ถ้า login ไม่ได้หรือ upload รูปไม่ได้ ติดต่อ: [CONTACT]
```

## Step 10 — During launch monitoring

Every 15–30 minutes during the first launch window:

- [ ] check backend health
- [ ] check Admin Progress completion
- [ ] check disk usage if many photos are uploaded
- [ ] create backup after major response waves

Useful commands:

```bash
curl http://127.0.0.1:8030/health
cd /opt/data/as-survey-system && python3 scripts/as_survey_backup.py
```
