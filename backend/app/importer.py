from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
import json
import re
import shutil
import sqlite3
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from . import db
from .security import hash_pin

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _cell_index(cell_ref: str) -> int:
    letters = re.match(r"([A-Z]+)", cell_ref).group(1)
    idx = 0
    for ch in letters:
        idx = idx * 26 + ord(ch) - 64
    return idx - 1


def _text(el) -> str:
    return "" if el is None else "".join(el.itertext())


def read_xlsx(path: Path | str) -> dict[str, list[dict[str, str]]]:
    path = Path(path)
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = [_text(si) for si in root.findall("m:si", NS)]

        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        relmap = {r.attrib["Id"]: r.attrib["Target"] for r in rels.findall("rel:Relationship", NS)}
        workbook: dict[str, list[dict[str, str]]] = {}
        for sheet in wb.findall("m:sheets/m:sheet", NS):
            sheet_name = sheet.attrib["name"]
            rid = sheet.attrib["{" + NS["r"] + "}id"]
            target = relmap[rid]
            sheet_path = "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
            root = ET.fromstring(z.read(sheet_path))
            rows: list[list[str]] = []
            for row in root.findall(".//m:sheetData/m:row", NS):
                values: list[str] = []
                for cell in row.findall("m:c", NS):
                    idx = _cell_index(cell.attrib["r"])
                    while len(values) <= idx:
                        values.append("")
                    cell_type = cell.attrib.get("t")
                    if cell_type == "inlineStr":
                        value = _text(cell.find("m:is", NS))
                    else:
                        v = cell.find("m:v", NS)
                        value = v.text if v is not None and v.text is not None else ""
                        if cell_type == "s" and value != "":
                            value = shared[int(value)]
                    values[idx] = str(value).strip()
                rows.append(values)
            if not rows:
                workbook[sheet_name] = []
                continue
            headers = [h.strip() for h in rows[0]]
            records = []
            for raw in rows[1:]:
                if not any(str(x).strip() for x in raw):
                    continue
                records.append({headers[i]: (raw[i].strip() if i < len(raw) else "") for i in range(len(headers))})
            workbook[sheet_name] = records
        return workbook


def _bool(value: str) -> int:
    return 1 if str(value).strip().lower() in {"true", "1", "yes", "y"} else 0


def _status(value: str, default: str = "active") -> str:
    v = str(value or default).strip().lower().replace(" ", "_")
    return v or default


def _task_status(value: str) -> str:
    v = _status(value, "new")
    return v if v in {"new", "pending", "submitted", "overdue", "reopened"} else "new"


def validate_workbook(data: dict[str, list[dict[str, str]]]) -> dict:
    errors: list[str] = []
    counts = {k: len(v) for k, v in data.items()}

    def dup(sheet: str, key: str):
        seen = set()
        for row in data.get(sheet, []):
            val = row.get(key, "")
            if not val:
                errors.append(f"{sheet}: missing {key}")
            elif val in seen:
                errors.append(f"{sheet}: duplicate {key} {val}")
            seen.add(val)

    for sheet, rows in data.items():
        for idx, row in enumerate(rows, start=2):
            for key, value in row.items():
                if str(value).strip().startswith("#"):
                    errors.append(f"{sheet}: Excel error token at row {idx} column {key}: {value}")

    dup("AS_USERS", "as_code")
    dup("BRANCHES", "branch_code")
    dup("SURVEYS", "survey_id")
    dup("SURVEY_BRANCHES", "task_id")

    as_codes = {r.get("as_code") for r in data.get("AS_USERS", [])}
    branches = {r.get("branch_code") for r in data.get("BRANCHES", [])}
    surveys = {r.get("survey_id") for r in data.get("SURVEYS", [])}
    tasks = {r.get("task_id") for r in data.get("SURVEY_BRANCHES", [])}
    survey_questions = {(r.get("survey_id"), r.get("question_id")) for r in data.get("QUESTIONS", [])}
    responses = {r.get("response_id") for r in data.get("RESPONSES", [])}

    for r in data.get("BRANCHES", []):
        if r.get("assigned_as_code") not in as_codes:
            errors.append(f"BRANCHES: assigned AS missing {r.get('assigned_as_code')}")
    for r in data.get("AS_USERS", []):
        if not str(r.get("pin", "")).strip():
            errors.append(f"AS_USERS: missing pin for {r.get('as_code')}")
    for r in data.get("SURVEYS", []):
        if not r.get("deadline"):
            errors.append(f"SURVEYS: missing deadline {r.get('survey_id')}")
    for r in data.get("SURVEY_BRANCHES", []):
        if r.get("survey_id") not in surveys:
            errors.append(f"SURVEY_BRANCHES: survey missing {r.get('survey_id')}")
        if r.get("branch_code") not in branches:
            errors.append(f"SURVEY_BRANCHES: branch missing {r.get('branch_code')}")
        if r.get("assigned_as_code") not in as_codes:
            errors.append(f"SURVEY_BRANCHES: AS missing {r.get('assigned_as_code')}")
    for r in data.get("QUESTIONS", []):
        if r.get("survey_id") not in surveys:
            errors.append(f"QUESTIONS: survey missing {r.get('survey_id')}")
        if not str(r.get("answer_type", "")).strip():
            errors.append(f"QUESTIONS: missing answer_type {r.get('question_id')}")
    for r in data.get("RESPONSES", []):
        if r.get("task_id") not in tasks:
            errors.append(f"RESPONSES: task missing {r.get('task_id')}")
        if (r.get("survey_id"), r.get("question_id")) not in survey_questions:
            errors.append(f"RESPONSES: question missing {r.get('survey_id')}/{r.get('question_id')}")
    for r in data.get("RESPONSE_FILES", []):
        if r.get("response_id") not in responses:
            errors.append(f"RESPONSE_FILES: response missing {r.get('response_id')}")
    for r in data.get("STATUS_LOG", []):
        if r.get("task_id") not in tasks:
            errors.append(f"STATUS_LOG: task missing {r.get('task_id')}")

    summary = {
        "error_count": len(errors),
        "as_user_count": counts.get("AS_USERS", 0),
        "branch_count": counts.get("BRANCHES", 0),
        "survey_count": counts.get("SURVEYS", 0),
        "task_count": counts.get("SURVEY_BRANCHES", 0),
        "question_count": counts.get("QUESTIONS", 0),
    }
    return {"valid": not errors, "errors": errors, "counts": counts, "summary": summary}


def _id_map(conn, table: str, code_col: str) -> dict[str, int]:
    return {r[code_col]: r["id"] for r in conn.execute(f"SELECT id,{code_col} FROM {table}")}


def import_data(data: dict[str, list[dict[str, str]]], db_path: Path | str = db.DB_PATH) -> dict:
    result = validate_workbook(data)
    if not result["valid"]:
        return result
    conn = db.connect(db_path)
    with conn:
        # Idempotent MVP import: clear mutable data then reload.
        for table in ["response_files", "survey_answers", "survey_responses", "status_logs", "survey_questions", "survey_tasks", "survey_selected_branches", "surveys", "branches", "users", "admin_settings"]:
            conn.execute(f"DELETE FROM {table}")
        for row in data.get("AS_USERS", []):
            role = "as" if row.get("role", "AS").strip().lower() == "as" else "super_admin"
            conn.execute(
                "INSERT INTO users(login_code,name,region,phone,email,pin_hash,role,status) VALUES(?,?,?,?,?,?,?,?)",
                (row["as_code"], row.get("as_name", row["as_code"]), row.get("region"), row.get("phone"), row.get("email"), hash_pin(row.get("pin", "0000")), role, _status(row.get("status"))),
            )
        conn.execute(
            "INSERT INTO users(login_code,name,pin_hash,role,status) VALUES(?,?,?,?,?)",
            ("ADM01", "Admin", hash_pin("0000"), "super_admin", "active"),
        )
        users = _id_map(conn, "users", "login_code")
        for row in data.get("BRANCHES", []):
            conn.execute(
                "INSERT INTO branches(branch_code,branch_name,account,region,province,assigned_user_id,status,note) VALUES(?,?,?,?,?,?,?,?)",
                (row["branch_code"], row.get("branch_name"), row.get("account"), row.get("region"), row.get("province"), users[row.get("assigned_as_code")], _status(row.get("status")), row.get("note")),
            )
        for row in data.get("SURVEYS", []):
            conn.execute(
                "INSERT INTO surveys(survey_code,title,category,description,deadline,status,created_by_user_id,created_at,published_at,closed_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (row["survey_id"], row.get("survey_title"), row.get("category"), row.get("description"), row.get("deadline"), _status(row.get("status"), "draft"), users.get(row.get("created_by")), row.get("created_at") or None, row.get("published_at") or None, row.get("closed_at") or None, row.get("updated_at") or None),
            )
        branches = _id_map(conn, "branches", "branch_code")
        surveys = _id_map(conn, "surveys", "survey_code")
        for row in data.get("SURVEY_BRANCHES", []):
            sid, bid = surveys[row["survey_id"]], branches[row["branch_code"]]
            conn.execute("INSERT OR IGNORE INTO survey_selected_branches(survey_id,branch_id,selected_by_user_id,confirmed_at) VALUES(?,?,?,CURRENT_TIMESTAMP)", (sid, bid, users.get("ADM01")))
            conn.execute(
                "INSERT INTO survey_tasks(task_code,survey_id,branch_id,assigned_user_id,deadline,status,assigned_at,submitted_at,last_updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (row["task_id"], sid, bid, users[row["assigned_as_code"]], row.get("deadline"), _task_status(row.get("task_status")), row.get("assigned_at") or None, row.get("submitted_at") or None, row.get("last_updated_at") or None),
            )
        for row in data.get("QUESTIONS", []):
            opts = [o for o in row.get("options", "").split("|") if o]
            conn.execute(
                "INSERT INTO survey_questions(survey_id,question_code,question_order,question_text,answer_type,required,allow_photo,photo_required,options_json,help_text) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (surveys[row["survey_id"]], row["question_id"], int(row.get("question_order") or 0), row.get("question_text"), row.get("answer_type"), _bool(row.get("required")), _bool(row.get("allow_photo")), _bool(row.get("photo_required")), json.dumps(opts, ensure_ascii=False) if opts else None, row.get("help_text")),
            )
        tasks = _id_map(conn, "survey_tasks", "task_code")
        qrows = conn.execute("SELECT q.id, q.question_code, s.survey_code FROM survey_questions q JOIN surveys s ON s.id=q.survey_id").fetchall()
        questions = {(r["survey_code"], r["question_code"]): r["id"] for r in qrows}
        response_group_ids: dict[str, int] = {}
        for response_code, rows in _group(data.get("RESPONSES", []), "response_id").items():
            first = rows[0]
            cur = conn.execute("INSERT INTO survey_responses(response_code,task_id,submitted_by_user_id,submitted_at,edit_version) VALUES(?,?,?,?,?)", (response_code, tasks[first["task_id"]], users[first.get("submitted_by")], first.get("submitted_at") or None, int(first.get("edit_version") or 1)))
            response_group_ids[response_code] = cur.lastrowid
            for r in rows:
                qid = questions[(r["survey_id"], r["question_id"])]
                ans = r.get("answer_value")
                num = float(ans) if str(ans).replace(".", "", 1).isdigit() else None
                answer_json = json.dumps(ans.split("|"), ensure_ascii=False) if "|" in str(ans) else None
                conn.execute("INSERT INTO survey_answers(response_id,question_id,answer_text,answer_number,answer_json) VALUES(?,?,?,?,?)", (cur.lastrowid, qid, ans, num, answer_json))
        task_info = {r["task_code"]: r for r in conn.execute("SELECT t.task_code,t.id task_id,t.survey_id,t.branch_id FROM survey_tasks t")}
        for row in data.get("RESPONSE_FILES", []):
            # Resolve task through response row.
            resp_row = next((r for r in data.get("RESPONSES", []) if r.get("response_id") == row.get("response_id")), None)
            if not resp_row:
                continue
            ti = task_info[resp_row["task_id"]]
            qid = questions[(row["survey_id"], row["question_id"])]
            conn.execute(
                "INSERT INTO response_files(file_code,response_id,survey_id,task_id,branch_id,question_id,file_name,file_url,file_type,uploaded_by_user_id,uploaded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (row["file_id"], response_group_ids[row["response_id"]], ti["survey_id"], ti["task_id"], ti["branch_id"], qid, row.get("file_name"), row.get("file_url"), row.get("file_type"), users.get(row.get("uploaded_by")), row.get("uploaded_at") or None),
            )
        for row in data.get("STATUS_LOG", []):
            ti = task_info[row["task_id"]]
            changed = users.get(row.get("changed_by"))
            conn.execute("INSERT INTO status_logs(log_code,task_id,survey_id,branch_id,old_status,new_status,changed_by_user_id,changed_by_code,changed_at,note) VALUES(?,?,?,?,?,?,?,?,?,?)", (row["log_id"], ti["task_id"], ti["survey_id"], ti["branch_id"], _task_status(row.get("old_status")) if row.get("old_status") else None, _task_status(row.get("new_status")), changed, row.get("changed_by"), row.get("changed_at") or None, row.get("note")))
        for row in data.get("ADMIN_SETTINGS", []):
            conn.execute("INSERT INTO admin_settings(setting_key,setting_value,description) VALUES(?,?,?)", (row.get("setting_key"), row.get("setting_value"), row.get("description")))
    return result


def _group(rows: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        out[row[key]].append(row)
    return out


def backup_current_database(db_path: Path | str, uploads_dir: Path | str | None = None, output_dir: Path | str | None = None) -> dict:
    db_path = Path(db_path)
    backend_dir = db_path.parent
    uploads_dir = Path(uploads_dir) if uploads_dir is not None else backend_dir / "uploads"
    output_dir = Path(output_dir) if output_dir is not None else backend_dir.parent / "backups"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = output_dir / f"as-survey-import-backup-{stamp}"
    suffix = 0
    while backup_dir.exists():
        suffix += 1
        backup_dir = output_dir / f"as-survey-import-backup-{stamp}-{suffix}"
    backup_dir.mkdir(parents=True)
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_dir / "as_survey.db"))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    if uploads_dir.exists():
        shutil.copytree(uploads_dir, backup_dir / "uploads")
    else:
        (backup_dir / "uploads").mkdir()
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_db": str(db_path),
        "database": str(backup_dir / "as_survey.db"),
        "uploads": str(backup_dir / "uploads"),
        "backup_dir": str(backup_dir),
        "reason": "before_import",
    }
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def import_master_data(data: dict[str, list[dict[str, str]]], db_path: Path | str = db.DB_PATH) -> dict:
    """Upsert AS_USERS, BRANCHES, and ADMIN_SETTINGS only.

    This intentionally preserves surveys, tasks, responses, files, and the
    existing super_admin/admin PIN. It is for master-data workbook refreshes
    before a pilot launch.
    """
    conn = db.connect(db_path)
    with conn:
        for row in data.get("AS_USERS", []):
            role = "as" if row.get("role", "AS").strip().lower() == "as" else "super_admin"
            if role != "as":
                continue
            code = row["as_code"].strip()
            existing = conn.execute("SELECT id FROM users WHERE login_code=?", (code,)).fetchone()
            values = (
                row.get("as_name", code),
                row.get("region"),
                row.get("phone"),
                row.get("email"),
                hash_pin(row.get("pin", "")),
                "as",
                _status(row.get("status")),
            )
            if existing:
                conn.execute(
                    """
                    UPDATE users
                    SET name=?, region=?, phone=?, email=?, pin_hash=?, role=?, status=?, updated_at=CURRENT_TIMESTAMP
                    WHERE login_code=?
                    """,
                    (*values, code),
                )
            else:
                conn.execute(
                    "INSERT INTO users(login_code,name,region,phone,email,pin_hash,role,status) VALUES(?,?,?,?,?,?,?,?)",
                    (code, *values),
                )

        users = _id_map(conn, "users", "login_code")
        for row in data.get("BRANCHES", []):
            code = row["branch_code"].strip()
            assigned_code = row["assigned_as_code"].strip()
            assigned_user_id = users[assigned_code]
            values = (
                row.get("branch_name", code),
                row.get("account"),
                row.get("region"),
                row.get("province"),
                assigned_user_id,
                _status(row.get("status")),
                row.get("note"),
            )
            existing = conn.execute("SELECT id FROM branches WHERE branch_code=?", (code,)).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE branches
                    SET branch_name=?, account=?, region=?, province=?, assigned_user_id=?, status=?, note=?, updated_at=CURRENT_TIMESTAMP
                    WHERE branch_code=?
                    """,
                    (*values, code),
                )
            else:
                conn.execute(
                    "INSERT INTO branches(branch_code,branch_name,account,region,province,assigned_user_id,status,note) VALUES(?,?,?,?,?,?,?,?)",
                    (code, *values),
                )

        for row in data.get("ADMIN_SETTINGS", []):
            conn.execute(
                """
                INSERT INTO admin_settings(setting_key, setting_value, description, updated_at)
                VALUES(?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(setting_key) DO UPDATE SET
                  setting_value=excluded.setting_value,
                  description=excluded.description,
                  updated_at=CURRENT_TIMESTAMP
                """,
                (row.get("setting_key"), row.get("setting_value"), row.get("description")),
            )

    return {
        "valid": True,
        "mode": "master_data",
        "imported": {
            "as_users": len([r for r in data.get("AS_USERS", []) if r.get("role", "AS").strip().lower() == "as"]),
            "branches": len(data.get("BRANCHES", [])),
            "admin_settings": len(data.get("ADMIN_SETTINGS", [])),
        },
    }


def import_master_data_workbook(path: Path | str, db_path: Path | str = db.DB_PATH, dry_run: bool = False, backup_before_import: bool = False) -> dict:
    data = read_xlsx(path)
    result = validate_workbook(data)
    result["dry_run"] = dry_run
    result["mode"] = "master_data"
    if dry_run or not result["valid"]:
        return result
    backup = None
    if backup_before_import and Path(db_path).exists():
        backup = backup_current_database(db_path)
    imported = import_master_data(data, db_path=db_path)
    imported["dry_run"] = False
    if backup:
        imported["backup_dir"] = str(backup["backup_dir"])
    return imported


def import_workbook(path: Path | str, db_path: Path | str = db.DB_PATH, dry_run: bool = False, backup_before_import: bool = False) -> dict:
    data = read_xlsx(path)
    result = validate_workbook(data)
    result["dry_run"] = dry_run
    if dry_run or not result["valid"]:
        return result
    backup = None
    if backup_before_import and Path(db_path).exists():
        backup = backup_current_database(db_path)
    imported = import_data(data, db_path=db_path)
    imported["dry_run"] = False
    if backup:
        imported["backup_dir"] = backup["backup_dir"]
    return imported


def import_upload_bytes(content: bytes, filename: str, db_path: Path | str = db.DB_PATH, dry_run: bool = False, backup_before_import: bool = False) -> dict:
    suffix = Path(filename).suffix or ".xlsx"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        return import_workbook(tmp_path, db_path=db_path, dry_run=dry_run, backup_before_import=backup_before_import)
    finally:
        tmp_path.unlink(missing_ok=True)
