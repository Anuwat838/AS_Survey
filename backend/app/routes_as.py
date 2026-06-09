from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import json
import re
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from . import db
from .deps import get_db_path, require_as
from .response_utils import latest_response_for_task

router = APIRouter(prefix="/api/as", tags=["as"])


class AnswerPayload(BaseModel):
    question_id: int
    answer: str | int | float | list[str] | None = None
    files: list[dict] = []


class SubmitPayload(BaseModel):
    answers: list[AnswerPayload]


def _task_rows(conn, user_id: int):
    return conn.execute(
        """
        SELECT t.id,t.task_code,t.status,t.deadline,t.submitted_at,
               s.id survey_id,s.survey_code,s.title,s.category,s.deadline survey_deadline,s.status survey_status,
               b.branch_code,b.branch_name,b.account,b.region,u.login_code assigned_as_code
        FROM survey_tasks t
        JOIN surveys s ON s.id=t.survey_id
        JOIN branches b ON b.id=t.branch_id
        JOIN users u ON u.id=t.assigned_user_id
        WHERE t.assigned_user_id=? AND s.status <> 'deleted'
        ORDER BY s.deadline, s.id, t.deadline, b.branch_name
        """,
        (user_id,),
    ).fetchall()


def _shape_task(row):
    return {
        "id": row["id"],
        "task_code": row["task_code"],
        "status": row["status"],
        "deadline": row["deadline"],
        "submitted_at": row["submitted_at"],
        "branch_code": row["branch_code"],
        "branch_name": row["branch_name"],
        "account": row["account"],
        "region": row["region"],
        "assigned_as_code": row["assigned_as_code"],
    }


@router.get("/tasks")
def list_tasks(user: dict = Depends(require_as), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    grouped = OrderedDict()
    for row in _task_rows(conn, user["id"]):
        grouped.setdefault(row["survey_id"], {
            "survey_id": row["survey_id"],
            "survey_code": row["survey_code"],
            "title": row["title"],
            "category": row["category"],
            "deadline": row["survey_deadline"],
            "status": row["survey_status"],
            "tasks": [],
        })["tasks"].append(_shape_task(row))
    active, completed = [], []
    for survey in grouped.values():
        if survey["tasks"] and all(t["status"] == "submitted" for t in survey["tasks"]):
            completed.append(survey)
        else:
            active.append(survey)
    return {"active_surveys": active, "completed_surveys": completed}


MAX_PHOTOS_PER_QUESTION = 5
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}


def _safe_file_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name or "photo.jpg").name).strip("._")
    return cleaned or "photo.jpg"


def _upload_root(db_path) -> Path:
    root = Path(db_path).parent / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


@router.get("/tasks/{task_id}")
def task_detail(task_id: int, user: dict = Depends(require_as), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    task = conn.execute(
        """
        SELECT t.*,s.survey_code,s.title,s.category,b.branch_code,b.branch_name,b.account,b.region
        FROM survey_tasks t JOIN surveys s ON s.id=t.survey_id JOIN branches b ON b.id=t.branch_id
        WHERE t.id=? AND t.assigned_user_id=?
        """,
        (task_id, user["id"]),
    ).fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    questions = []
    for q in conn.execute("SELECT * FROM survey_questions WHERE survey_id=? ORDER BY question_order", (task["survey_id"],)):
        item = db.row_to_dict(q)
        item["options"] = json.loads(item["options_json"] or "[]")
        questions.append(item)
    payload = db.row_to_dict(task)
    payload["questions"] = questions
    payload["latest_response"] = latest_response_for_task(conn, task_id)
    return payload


@router.post("/tasks/{task_id}/questions/{question_id}/files")
async def upload_question_files(
    task_id: int,
    question_id: int,
    files: list[UploadFile] = File(...),
    user: dict = Depends(require_as),
    db_path=Depends(get_db_path),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    if len(files) > MAX_PHOTOS_PER_QUESTION:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_PHOTOS_PER_QUESTION} photos per question")
    conn = db.connect(db_path)
    task = conn.execute("SELECT * FROM survey_tasks WHERE id=? AND assigned_user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    question = conn.execute(
        "SELECT * FROM survey_questions WHERE id=? AND survey_id=?",
        (question_id, task["survey_id"]),
    ).fetchone()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    if not (question["allow_photo"] or question["photo_required"] or question["answer_type"] == "photo"):
        raise HTTPException(status_code=400, detail="This question does not allow photos")

    upload_dir = _upload_root(db_path) / f"task_{task_id}" / f"question_{question_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for upload in files:
        if upload.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Only image files are allowed")
        content = await upload.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=400, detail="File is too large")
        original = _safe_file_name(upload.filename or "photo.jpg")
        ext = Path(original).suffix.lower() or ALLOWED_IMAGE_TYPES[upload.content_type]
        if ext not in ALLOWED_IMAGE_TYPES.values():
            ext = ALLOWED_IMAGE_TYPES[upload.content_type]
        stored_name = f"{uuid.uuid4().hex}{ext}"
        path = upload_dir / stored_name
        path.write_bytes(content)
        rel = f"/uploads/task_{task_id}/question_{question_id}/{stored_name}"
        saved.append({
            "file_name": original,
            "file_url": rel,
            "file_path": str(path),
            "file_type": upload.content_type,
        })
    return {"ok": True, "count": len(saved), "files": saved}


@router.post("/tasks/{task_id}/submit")
def submit_task(task_id: int, payload: SubmitPayload, user: dict = Depends(require_as), db_path=Depends(get_db_path)):
    conn = db.connect(db_path)
    task = conn.execute("SELECT * FROM survey_tasks WHERE id=? AND assigned_user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    questions = conn.execute("SELECT * FROM survey_questions WHERE survey_id=?", (task["survey_id"],)).fetchall()
    answers_by_q = {a.question_id: a for a in payload.answers}
    for q in questions:
        ans = answers_by_q.get(q["id"])
        if q["required"] and (ans is None or ans.answer in (None, "", [])):
            raise HTTPException(status_code=400, detail=f"Missing required answer: {q['question_code']}")
        if ans and q["answer_type"] == "number":
            try:
                float(ans.answer)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Invalid number answer: {q['question_code']}") from exc
        if q["photo_required"] and (ans is None or not ans.files):
            raise HTTPException(status_code=400, detail=f"Missing required photo: {q['question_code']}")
    with conn:
        code = f"RSP-API-{task_id}-{user['id']}"
        conn.execute("DELETE FROM survey_responses WHERE task_id=?", (task_id,))
        cur = conn.execute("INSERT INTO survey_responses(response_code,task_id,submitted_by_user_id) VALUES(?,?,?)", (code, task_id, user["id"]))
        response_id = cur.lastrowid
        for ans in payload.answers:
            q = conn.execute("SELECT * FROM survey_questions WHERE id=? AND survey_id=?", (ans.question_id, task["survey_id"])).fetchone()
            if not q:
                continue
            value = ans.answer
            text = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else (None if value is None else str(value))
            number = float(value) if q["answer_type"] == "number" and value not in (None, "") else None
            cur_ans = conn.execute("INSERT INTO survey_answers(response_id,question_id,answer_text,answer_number,answer_json) VALUES(?,?,?,?,?)", (response_id, ans.question_id, text, number, json.dumps(value, ensure_ascii=False) if isinstance(value, list) else None))
            for idx, f in enumerate(ans.files or []):
                conn.execute("INSERT INTO response_files(file_code,response_id,answer_id,survey_id,task_id,branch_id,question_id,file_name,file_url,file_path,file_type,uploaded_by_user_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (f"FILE-API-{task_id}-{ans.question_id}-{idx}", response_id, cur_ans.lastrowid, task["survey_id"], task_id, task["branch_id"], ans.question_id, f.get("file_name", "photo.jpg"), f.get("file_url"), f.get("file_path"), f.get("file_type", "image/jpeg"), user["id"]))
        old = task["status"]
        conn.execute("UPDATE survey_tasks SET status='submitted', submitted_at=CURRENT_TIMESTAMP,last_updated_at=CURRENT_TIMESTAMP WHERE id=?", (task_id,))
        conn.execute("INSERT INTO status_logs(log_code,task_id,survey_id,branch_id,old_status,new_status,changed_by_user_id,changed_by_code,note) VALUES(?,?,?,?,?,?,?,?,?)", (f"LOG-API-{task_id}-{response_id}", task_id, task["survey_id"], task["branch_id"], old, "submitted", user["id"], user["login_code"], "Submitted from API"))
    return {"ok": True, "task_id": task_id, "status": "submitted", "response_id": response_id}
