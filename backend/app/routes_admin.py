from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from . import db
from .deps import get_db_path, require_admin
from .response_utils import responses_for_survey
from .security import hash_pin, verify_pin

router = APIRouter(prefix="/api/admin", tags=["admin"])


class SurveyCreate(BaseModel):
    title: str
    category: str | None = None
    description: str | None = None
    deadline: str


class BranchSelection(BaseModel):
    branch_codes: list[str]


class QuestionCreate(BaseModel):
    question_order: int | None = None
    question_text: str
    answer_type: str = "short_text"
    required: bool = True
    allow_photo: bool = False
    photo_required: bool = False
    options: list[str] = []
    help_text: str | None = None


class UserCreate(BaseModel):
    login_code: str
    name: str
    region: str | None = None
    phone: str | None = None
    email: str | None = None
    role: str = "as"
    status: str = "active"
    pin: str


class UserUpdate(BaseModel):
    login_code: str | None = None
    name: str | None = None
    region: str | None = None
    phone: str | None = None
    email: str | None = None
    role: str | None = None
    status: str | None = None


class AdminPinReset(BaseModel):
    new_pin: str


def _next_code(conn, table: str, id_col: str, prefix: str, width: int = 4) -> str:
    row = conn.execute(f"SELECT COALESCE(MAX(id),0)+1 n FROM {table}").fetchone()
    return f"{prefix}-{int(row['n']):0{width}d}"


def _require_draft(conn, survey_id: int):
    survey = conn.execute("SELECT * FROM surveys WHERE id=? AND status='draft'", (survey_id,)).fetchone()
    if not survey:
        raise HTTPException(status_code=404, detail="Draft survey not found")
    return survey


def _clean_user(row) -> dict:
    data = db.row_to_dict(row)
    data.pop("pin_hash", None)
    return data


def _validate_role_status(role: str, status: str):
    if role not in {"as", "super_admin"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    if status not in {"active", "inactive"}:
        raise HTTPException(status_code=400, detail="Invalid status")


def _validate_pin(pin: str):
    value = str(pin or "").strip()
    if len(value) < 6 or not value.isdigit():
        raise HTTPException(status_code=400, detail="PIN must be at least 6 digits")


@router.get("/users")
def list_users(role: str | None = None, status: str | None = None, q: str | None = None, user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    where = ["1=1"]
    params = []
    if role:
        where.append("role=?")
        params.append(role)
    if status:
        where.append("status=?")
        params.append(status)
    if q:
        where.append("(login_code LIKE ? OR name LIKE ? OR phone LIKE ? OR email LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
    rows = conn.execute(f"SELECT * FROM users WHERE {' AND '.join(where)} ORDER BY role, login_code LIMIT 500", params).fetchall()
    return {"items": [_clean_user(r) for r in rows]}


@router.post("/users")
def create_user(payload: UserCreate, user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    login_code = payload.login_code.strip().upper()
    name = payload.name.strip()
    role = payload.role.strip()
    status = payload.status.strip()
    if not login_code or not name:
        raise HTTPException(status_code=400, detail="login_code and name are required")
    _validate_role_status(role, status)
    _validate_pin(payload.pin)
    conn = db.connect(db_path)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO users(login_code,name,region,phone,email,pin_hash,role,status) VALUES(?,?,?,?,?,?,?,?)",
                (login_code, name, payload.region, payload.phone, payload.email, hash_pin(payload.pin.strip()), role, status),
            )
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise HTTPException(status_code=400, detail="login_code already exists")
        raise
    row = conn.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    return {"user": _clean_user(row)}


@router.patch("/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate, user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    existing = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    data = payload.model_dump(exclude_unset=True)
    if "login_code" in data and data["login_code"] is not None:
        data["login_code"] = data["login_code"].strip().upper()
    role = data.get("role", existing["role"])
    status = data.get("status", existing["status"])
    _validate_role_status(role, status)
    fields = []
    params = []
    for key in ["login_code", "name", "region", "phone", "email", "role", "status"]:
        if key in data:
            fields.append(f"{key}=?")
            params.append(data[key])
    if fields:
        fields.append("updated_at=CURRENT_TIMESTAMP")
        params.append(user_id)
        try:
            with conn:
                conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id=?", params)
        except Exception as exc:
            if "UNIQUE" in str(exc):
                raise HTTPException(status_code=400, detail="login_code already exists")
            raise
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return {"user": _clean_user(row)}


@router.post("/users/{user_id}/pin")
def reset_user_pin(user_id: int, payload: AdminPinReset, user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    _validate_pin(payload.new_pin)
    conn = db.connect(db_path)
    row = conn.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    with conn:
        conn.execute("UPDATE users SET pin_hash=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (hash_pin(payload.new_pin.strip()), user_id))
    return {"ok": True}


def _parse_branch_csv(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    required = {"branch_code", "branch_name", "account", "region", "assigned_as_code"}
    if not reader.fieldnames or not required.issubset({h.strip() for h in reader.fieldnames}):
        raise HTTPException(status_code=400, detail="CSV must include: branch_code,branch_name,account,region,assigned_as_code")
    rows = []
    for idx, row in enumerate(reader, start=2):
        cleaned = {str(k or "").strip(): str(v or "").strip() for k, v in row.items()}
        if not any(cleaned.values()):
            continue
        for key in required:
            if not cleaned.get(key):
                raise HTTPException(status_code=400, detail=f"row {idx}: missing {key}")
        cleaned["branch_code"] = cleaned["branch_code"].upper()
        cleaned["assigned_as_code"] = cleaned["assigned_as_code"].upper()
        cleaned["status"] = (cleaned.get("status") or "active").lower()
        if cleaned["status"] not in {"active", "inactive"}:
            raise HTTPException(status_code=400, detail=f"row {idx}: invalid status")
        rows.append(cleaned)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV has no branch rows")
    return rows


@router.post("/branches/import-csv")
async def import_branches_csv(dry_run: bool = False, file: UploadFile = File(...), user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    raw = await file.read()
    rows = _parse_branch_csv(raw)
    conn = db.connect(db_path)
    as_ids = {r["login_code"]: r["id"] for r in conn.execute("SELECT id,login_code FROM users WHERE role='as'")}
    errors = []
    seen = set()
    for idx, row in enumerate(rows, start=2):
        if row["branch_code"] in seen:
            errors.append(f"row {idx}: duplicate branch_code {row['branch_code']}")
        seen.add(row["branch_code"])
        if row["assigned_as_code"] not in as_ids:
            errors.append(f"row {idx}: assigned AS missing {row['assigned_as_code']}")
    summary = {"rows": len(rows), "inserted": 0, "updated": 0, "errors": len(errors)}
    if errors:
        raise HTTPException(status_code=400, detail={"valid": False, "errors": errors, "summary": summary})
    for row in rows:
        exists = conn.execute("SELECT id FROM branches WHERE branch_code=?", (row["branch_code"],)).fetchone()
        if exists:
            summary["updated"] += 1
        else:
            summary["inserted"] += 1
    if not dry_run:
        with conn:
            for row in rows:
                existing = conn.execute("SELECT id FROM branches WHERE branch_code=?", (row["branch_code"],)).fetchone()
                values = (row["branch_name"], row["account"], row["region"], row.get("province"), as_ids[row["assigned_as_code"]], row["status"], row.get("note"))
                if existing:
                    conn.execute(
                        "UPDATE branches SET branch_name=?,account=?,region=?,province=?,assigned_user_id=?,status=?,note=?,updated_at=CURRENT_TIMESTAMP WHERE branch_code=?",
                        (*values, row["branch_code"]),
                    )
                else:
                    conn.execute(
                        "INSERT INTO branches(branch_code,branch_name,account,region,province,assigned_user_id,status,note) VALUES(?,?,?,?,?,?,?,?)",
                        (row["branch_code"], *values),
                    )
    return {"valid": True, "dry_run": dry_run, "summary": summary}


@router.get("/filters")
def admin_filters(user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    accounts = [r["account"] for r in conn.execute("SELECT DISTINCT account FROM branches WHERE status='active' ORDER BY account")]
    regions = [r["region"] for r in conn.execute("SELECT DISTINCT region FROM branches WHERE status='active' ORDER BY region")]
    as_codes = [r["login_code"] for r in conn.execute("SELECT login_code FROM users WHERE role='as' AND status='active' ORDER BY login_code")]
    return {"accounts": accounts, "regions": regions, "as_codes": as_codes}


@router.get("/branches")
def admin_branches(account: str | None = None, region: str | None = None, as_code: str | None = None, q: str | None = None, user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    where = ["b.status='active'", "u.status='active'"]
    params = []
    if account:
        where.append("b.account=?")
        params.append(account)
    if region:
        where.append("b.region=?")
        params.append(region)
    if as_code:
        where.append("u.login_code=?")
        params.append(as_code)
    if q:
        where.append("(b.branch_code LIKE ? OR b.branch_name LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    rows = conn.execute(
        f"""
        SELECT b.branch_code,b.branch_name,b.account,b.region,b.province,u.login_code assigned_as_code,u.name assigned_as_name,b.status
        FROM branches b JOIN users u ON u.id=b.assigned_user_id
        WHERE {' AND '.join(where)}
        ORDER BY b.account,b.region,u.login_code,b.branch_name
        LIMIT 500
        """,
        params,
    ).fetchall()
    return {"items": [db.row_to_dict(r) for r in rows]}


@router.post("/surveys")
def create_survey(payload: SurveyCreate, user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    if not payload.title.strip() or not payload.deadline.strip():
        raise HTTPException(status_code=400, detail="title and deadline are required")
    conn = db.connect(db_path)
    with conn:
        survey_code = _next_code(conn, "surveys", "id", "SVY")
        cur = conn.execute(
            "INSERT INTO surveys(survey_code,title,category,description,deadline,status,created_by_user_id) VALUES(?,?,?,?,?,'draft',?)",
            (survey_code, payload.title.strip(), payload.category, payload.description, payload.deadline.strip(), user["id"]),
        )
    return {"survey_id": cur.lastrowid, "survey_code": survey_code, "status": "draft"}


@router.post("/surveys/{survey_id}/selected-branches")
def add_selected_branches(survey_id: int, payload: BranchSelection, user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    _require_draft(conn, survey_id)
    added = duplicates = 0
    with conn:
        for code in payload.branch_codes:
            branch = conn.execute("SELECT id FROM branches WHERE branch_code=? AND status='active'", (code,)).fetchone()
            if not branch:
                raise HTTPException(status_code=400, detail=f"Branch not found: {code}")
            exists = conn.execute("SELECT 1 FROM survey_selected_branches WHERE survey_id=? AND branch_id=?", (survey_id, branch["id"])).fetchone()
            if exists:
                duplicates += 1
                continue
            conn.execute("INSERT INTO survey_selected_branches(survey_id,branch_id,selected_by_user_id,confirmed_at) VALUES(?,?,?,CURRENT_TIMESTAMP)", (survey_id, branch["id"], user["id"]))
            added += 1
    total = conn.execute("SELECT COUNT(*) c FROM survey_selected_branches WHERE survey_id=?", (survey_id,)).fetchone()["c"]
    return {"added": added, "duplicates": duplicates, "total_selected": total}


@router.get("/surveys/{survey_id}/selected-branches")
def get_selected_branches(survey_id: int, user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    rows = conn.execute(
        """
        SELECT b.branch_code,b.branch_name,b.account,b.region,u.login_code assigned_as_code,u.name assigned_as_name
        FROM survey_selected_branches sb
        JOIN branches b ON b.id=sb.branch_id
        JOIN users u ON u.id=b.assigned_user_id
        WHERE sb.survey_id=?
        ORDER BY b.account,b.region,b.branch_name
        """,
        (survey_id,),
    ).fetchall()
    return {"items": [db.row_to_dict(r) for r in rows]}


@router.post("/surveys/{survey_id}/questions")
def add_question(survey_id: int, payload: QuestionCreate, user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    _require_draft(conn, survey_id)
    answer_type = payload.answer_type
    if answer_type not in {"short_text", "long_text", "number", "single_choice", "multiple_choice", "photo"}:
        raise HTTPException(status_code=400, detail="Invalid answer_type")
    if payload.photo_required and not payload.allow_photo:
        raise HTTPException(status_code=400, detail="photo_required requires allow_photo")
    if answer_type in {"single_choice", "multiple_choice"} and not payload.options:
        raise HTTPException(status_code=400, detail="Choice questions require options")
    order = payload.question_order or (conn.execute("SELECT COALESCE(MAX(question_order),0)+1 n FROM survey_questions WHERE survey_id=?", (survey_id,)).fetchone()["n"])
    code = f"Q{order}"
    with conn:
        cur = conn.execute(
            """
            INSERT INTO survey_questions(survey_id,question_code,question_order,question_text,answer_type,required,allow_photo,photo_required,options_json,help_text)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (survey_id, code, order, payload.question_text.strip(), answer_type, int(payload.required), int(payload.allow_photo), int(payload.photo_required), json.dumps(payload.options, ensure_ascii=False) if payload.options else None, payload.help_text),
        )
    return {"question_id": cur.lastrowid, "question_code": code, "question_order": order}


@router.post("/surveys/{survey_id}/publish")
def publish_survey(survey_id: int, user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    survey = _require_draft(conn, survey_id)
    branches = conn.execute(
        """
        SELECT b.id branch_id,b.assigned_user_id
        FROM survey_selected_branches sb JOIN branches b ON b.id=sb.branch_id JOIN users u ON u.id=b.assigned_user_id
        WHERE sb.survey_id=? AND b.status='active' AND u.status='active'
        """,
        (survey_id,),
    ).fetchall()
    if not branches:
        raise HTTPException(status_code=400, detail="Select at least one branch before publish")
    qrows = conn.execute("SELECT answer_type,options_json FROM survey_questions WHERE survey_id=? ORDER BY question_order", (survey_id,)).fetchall()
    if not qrows:
        raise HTTPException(status_code=400, detail="Add at least one question before publish")
    for q in qrows:
        if q["answer_type"] in {"single_choice", "multiple_choice"} and not q["options_json"]:
            raise HTTPException(status_code=400, detail="Choice questions require options")
    created = 0
    with conn:
        for idx, row in enumerate(branches, start=1):
            task_code = f"{survey['survey_code']}-T{idx:04d}"
            conn.execute(
                "INSERT OR IGNORE INTO survey_tasks(task_code,survey_id,branch_id,assigned_user_id,deadline,status) VALUES(?,?,?,?,?,'new')",
                (task_code, survey_id, row["branch_id"], row["assigned_user_id"], survey["deadline"]),
            )
            if conn.total_changes:
                created += 1
        conn.execute("UPDATE surveys SET status='published', published_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?", (survey_id,))
    return {"survey_id": survey_id, "survey_code": survey["survey_code"], "created_tasks": len(branches), "status": "published"}


@router.get("/security/status")
def security_status(user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    admin = conn.execute("SELECT pin_hash FROM users WHERE login_code='ADM01' AND role='super_admin' AND status='active'").fetchone()
    default_pin = bool(admin and verify_pin("0000", admin["pin_hash"]))
    warnings = []
    if default_pin:
        warnings.append("Admin PIN is still the seed value; change it before launch")
    return {
        "admin_default_pin": default_pin,
        "launch_locked": default_pin,
        "warnings": warnings,
    }


@router.get("/surveys/progress")
def surveys_progress(user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    rows = [db.row_to_dict(r) for r in conn.execute("SELECT * FROM survey_progress ORDER BY deadline, survey_id")]
    return {"surveys": rows}


@router.get("/surveys/{survey_id}/progress")
def survey_progress_detail(survey_id: int, user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    survey = conn.execute("SELECT * FROM survey_progress WHERE survey_id=?", (survey_id,)).fetchone()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    by_as = [db.row_to_dict(r) for r in conn.execute("SELECT * FROM survey_progress_by_as WHERE survey_id=? ORDER BY as_code", (survey_id,))]
    return {"survey": db.row_to_dict(survey), "by_as": by_as}


@router.get("/surveys/{survey_id}/responses")
def survey_responses(survey_id: int, user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    survey = conn.execute("SELECT id FROM surveys WHERE id=? AND status <> 'deleted'", (survey_id,)).fetchone()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    return {"responses": responses_for_survey(conn, survey_id)}


@router.get("/surveys/{survey_id}/response-status")
def survey_response_status(survey_id: int, user: dict = Depends(require_admin), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    survey = conn.execute("SELECT id,title,category FROM surveys WHERE id=? AND status <> 'deleted'", (survey_id,)).fetchone()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    questions = [db.row_to_dict(r) for r in conn.execute(
        """
        SELECT id,required,allow_photo,photo_required
        FROM survey_questions
        WHERE survey_id=?
        ORDER BY question_order
        """,
        (survey_id,),
    )]
    qids = {q["id"] for q in questions}
    required_qids = {q["id"] for q in questions if q.get("required")}
    photo_qids = {q["id"] for q in questions if q.get("allow_photo") or q.get("photo_required")}
    photo_required_qids = {q["id"] for q in questions if q.get("photo_required")}
    rows = []
    tasks = conn.execute(
        """
        SELECT t.id task_id,t.task_code,t.status task_status,t.deadline,
               b.branch_code,b.branch_name,b.account,b.region,
               u.login_code assigned_as
        FROM survey_tasks t
        JOIN branches b ON b.id=t.branch_id
        JOIN users u ON u.id=t.assigned_user_id
        WHERE t.survey_id=?
        ORDER BY b.account,b.region,b.branch_name
        """,
        (survey_id,),
    ).fetchall()
    for task in tasks:
        response = conn.execute(
            "SELECT id,submitted_at,submitted_by_user_id FROM survey_responses WHERE task_id=? ORDER BY submitted_at DESC,id DESC LIMIT 1",
            (task["task_id"],),
        ).fetchone()
        answered_qids = set()
        file_qids = set()
        submitted_at = None
        if response:
            submitted_at = response["submitted_at"]
            for a in conn.execute("SELECT id,question_id,answer_text,answer_number,answer_json FROM survey_answers WHERE response_id=?", (response["id"],)):
                has_value = a["answer_number"] is not None or bool(a["answer_text"]) or bool(a["answer_json"])
                if has_value and a["question_id"] in qids:
                    answered_qids.add(a["question_id"])
                file_count = conn.execute("SELECT COUNT(*) c FROM response_files WHERE answer_id=?", (a["id"],)).fetchone()["c"]
                if file_count and a["question_id"] in photo_qids:
                    file_qids.add(a["question_id"])
        missing_required = len(required_qids - answered_qids)
        missing_required_photo = len(photo_required_qids - file_qids)
        if not response:
            answer_status = "not_submitted"
            photo_status = "not_submitted" if photo_qids else "not_required"
        else:
            answer_status = "complete" if missing_required == 0 else "incomplete"
            if not photo_qids:
                photo_status = "not_required"
            elif missing_required_photo:
                photo_status = "missing_required"
            elif file_qids:
                photo_status = "attached"
            else:
                photo_status = "not_attached"
        item = db.row_to_dict(task)
        item.update({
            "submitted": bool(response),
            "submitted_at": submitted_at,
            "question_count": len(questions),
            "required_question_count": len(required_qids),
            "answered_count": len(answered_qids),
            "required_answered_count": len(required_qids & answered_qids),
            "missing_required_count": missing_required,
            "photo_question_count": len(photo_qids),
            "photo_required_count": len(photo_required_qids),
            "photo_attached_count": len(file_qids),
            "missing_required_photo_count": missing_required_photo,
            "answer_status": answer_status,
            "photo_status": photo_status,
        })
        rows.append(item)
    return {"survey": db.row_to_dict(survey), "responses": rows}
