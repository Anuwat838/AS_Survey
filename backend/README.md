# AS Survey Backend MVP

Backend จริงชุดแรกสำหรับระบบ AS Survey ใช้ FastAPI + SQLite

## สถานะปัจจุบัน

- อ่านไฟล์ Excel blueprint ได้โดยไม่ต้องใช้ openpyxl
- Import ข้อมูลเข้า SQLite ได้
- AS/Admin login ด้วย `login_code + PIN`
- PIN ถูก hash ก่อนเก็บใน DB
- AS ดู task ที่ตัวเองรับผิดชอบ แยก Active/Completed ได้
- AS submit response ได้ผ่าน JSON
- Admin ดู progress และ import Excel ได้
- Admin มี launch lock/security status และเปลี่ยน PIN ตัวเองได้ก่อน pilot
- Session มี expiry configurable และ CORS จำกัด origin สำหรับ tunnel/prototype

## ติดตั้ง dependency

เครื่องนี้ไม่มี `apt` permission และไม่มี pip มาให้ตอนแรก Genos เลย bootstrap pip แบบ user-level แล้วติดตั้ง package ด้วย:

```bash
cd /opt/data/as-survey-system/backend
python3 -m pip install --user --break-system-packages -r requirements.txt
```

ถ้าเครื่องอื่นมี venv/pip ปกติ แนะนำใช้:

```bash
cd /opt/data/as-survey-system/backend
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

## สร้าง DB และ import Excel

ก่อน import ข้อมูลจริงสำหรับ pilot ให้ทำ dry-run ก่อนเสมอ เพื่อเช็ค duplicate/missing reference/missing PIN โดยยังไม่เขียน DB:

```bash
cd /opt/data/as-survey-system/backend
python3 - <<'PY'
from pathlib import Path
from app.importer import read_xlsx, validate_workbook
result = validate_workbook(read_xlsx(Path('/opt/data/cache/documents/as_survey_system_fixed.xlsx')))
print(result)
PY
```

ถ้าใช้ API Admin import ให้ส่ง query นี้เพื่อ validate อย่างเดียว:

```text
POST /api/admin/import/excel?dry_run=true
```

เมื่อ validation ผ่านแล้ว จึง import จริง:

```bash
cd /opt/data/as-survey-system/backend
python3 - <<'PY'
from pathlib import Path
from app.db import init_db, DB_PATH
from app.importer import import_workbook
init_db(DB_PATH)
result = import_workbook(Path('/opt/data/cache/documents/as_survey_system_fixed.xlsx'), db_path=DB_PATH, backup_before_import=True)
print(result)
PY
```

Admin API import จริงจะ backup DB+uploads ให้อัตโนมัติก่อนเขียน DB:

```text
POST /api/admin/import/excel
```

Validation report ตรวจหลัก ๆ:

- duplicate AS code / branch code / survey id / task id
- AS PIN ว่าง
- branch ที่ assign ไปยัง AS ที่ไม่มีอยู่
- survey ไม่มี deadline
- survey task อ้าง survey/branch/AS ที่ไม่มีอยู่
- question ไม่มี answer type
- response/file/status log อ้าง task/question/response ที่ไม่มีอยู่

## เปิด backend server

```bash
cd /opt/data/as-survey-system/backend
bash run.sh
```

URL หลัก:

- Health check: `http://YOUR_VPS_IP:8030/health`
- API docs: `http://YOUR_VPS_IP:8030/docs`

ถ้าเปิดจาก PC ผ่าน SSH tunnel:

```powershell
ssh -N -L 8030:127.0.0.1:8030 root@YOUR_VPS_IP
```

แล้วเปิดใน browser ของ PC:

```text
http://localhost:8030/docs
```

## Login ทดสอบ

AS ตัวอย่างจาก Excel:

- Login code: `BKK10`
- PIN: ดูจาก Excel blueprint หรือถาม Admin ผู้ดูแลข้อมูล

Admin MVP seed:

- Login code: `ADM01`
- PIN: `0000`

## Launch lock / เปลี่ยน Admin PIN

ก่อนส่ง link ให้ user จริง ต้อง clear launch lock นี้ก่อน:

1. Login Admin ที่ prototype หรือ API docs
2. เช็ค status:

```text
GET /api/admin/security/status
```

ถ้า response เป็น `launch_locked: true` เพราะ Admin PIN ยังเป็น seed `0000` ให้เปลี่ยน PIN:

```text
POST /api/auth/change-pin
Body: {"current_pin":"0000","new_pin":"เลขอย่างน้อย 6 หลัก"}
```

หลังเปลี่ยนแล้ว login ด้วย PIN ใหม่ และเช็คอีกครั้งให้ได้:

```text
admin_default_pin: false
launch_locked: false
```

Session/CORS config สำหรับ pilot:

```bash
export AS_SURVEY_SESSION_TTL_SECONDS=43200
export AS_SURVEY_ALLOWED_ORIGINS=http://localhost:8021,http://127.0.0.1:8021
```

## Test

```bash
cd /opt/data/as-survey-system/backend
python3 -m pytest tests/test_frontend_contract.py tests/test_backend_mvp.py tests/test_operational_readiness.py tests/test_import_safety.py tests/test_launch_security.py -q
```

Expected:

```text
all tests pass
```

## 60-user pilot readiness

Main runbook:

```text
/opt/data/as-survey-system/docs/pilot-launch-checklist.md
```

Pilot user smoke test script:

```bash
cd /opt/data/as-survey-system
python3 scripts/pilot_smoke_test.py --base-url http://127.0.0.1:8030 --users-csv /path/to/users.csv
```

The CSV must have `login_code,pin`. The script never prints PIN values.

Genos added the first operational hardening layer for a real pilot around 60 users:

- SQLite connections use `journal_mode=WAL` so readers and writers block each other less.
- SQLite connections use `busy_timeout=10000` so short write spikes wait instead of failing immediately with `database is locked`.
- SQLite `synchronous=NORMAL` keeps WAL reasonably safe while improving write performance for MVP/pilot use.
- Uploaded photos remain local under `backend/uploads/`; include this folder in every backup.

### Manual backup before/after pilot windows

Run this before importing real data, before big survey launches, and after important survey rounds:

```bash
cd /opt/data/as-survey-system
python3 scripts/as_survey_backup.py
```

Default backup output:

```text
/opt/data/as-survey-system/backups/as-survey-backup-YYYYMMDD_HHMMSS/
```

Each backup contains:

- `as_survey.db`
- `uploads/`
- `manifest.json`

## หมายเหตุความปลอดภัย

- ระบบนี้ยังเป็น MVP/dev server
- Session token ยังเก็บใน memory ถ้า restart server ต้อง login ใหม่ และตอนนี้มี expiry ตาม `AS_SURVEY_SESSION_TTL_SECONDS`
- Admin PIN `0000` ใช้เพื่อทดสอบเท่านั้น ต้องเปลี่ยนก่อนใช้จริง; ระบบมี launch lock เตือนจนกว่าจะเปลี่ยน
- CORS จำกัด origin ด้วย `AS_SURVEY_ALLOWED_ORIGINS`; อย่ากลับไปใช้ wildcard ก่อน pilot
- ยังควรใช้ HTTPS/reverse proxy ก่อนเปิดนอก tunnel ให้ผู้ใช้จริง
- รูป upload เก็บ local ใน `backend/uploads/`; ต้อง backup คู่กับ DB เสมอ
