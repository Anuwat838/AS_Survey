from __future__ import annotations

import json
from collections import OrderedDict

from . import db


def answer_value(row):
    if row['answer_json']:
        try:
            return json.loads(row['answer_json'])
        except Exception:
            return row['answer_json']
    if row['answer_number'] is not None:
        return row['answer_number']
    return row['answer_text']


def files_for_answer(conn, answer_id: int):
    return [
        db.row_to_dict(r)
        for r in conn.execute(
            """
            SELECT id,file_code,file_name,file_url,file_path,file_type,uploaded_at
            FROM response_files
            WHERE answer_id=?
            ORDER BY id
            """,
            (answer_id,),
        )
    ]


def response_detail(conn, response_id: int):
    response = conn.execute(
        """
        SELECT sr.id response_id,sr.response_code,sr.task_id,sr.submitted_at,
               u.login_code submitted_by,u.name submitted_by_name,
               t.task_code,t.status task_status,t.deadline task_deadline,
               s.id survey_id,s.title,s.category,s.deadline survey_deadline,
               b.branch_code,b.branch_name,b.account,b.region
        FROM survey_responses sr
        JOIN users u ON u.id=sr.submitted_by_user_id
        JOIN survey_tasks t ON t.id=sr.task_id
        JOIN surveys s ON s.id=t.survey_id
        JOIN branches b ON b.id=t.branch_id
        WHERE sr.id=?
        """,
        (response_id,),
    ).fetchone()
    if not response:
        return None
    payload = db.row_to_dict(response)
    answers = []
    for a in conn.execute(
        """
        SELECT a.id answer_id,a.question_id,a.answer_text,a.answer_number,a.answer_json,
               q.question_code,q.question_order,q.question_text,q.answer_type,q.required,q.allow_photo,q.photo_required
        FROM survey_answers a
        JOIN survey_questions q ON q.id=a.question_id
        WHERE a.response_id=?
        ORDER BY q.question_order
        """,
        (response_id,),
    ):
        item = db.row_to_dict(a)
        item['answer'] = answer_value(a)
        item['files'] = files_for_answer(conn, a['answer_id'])
        answers.append(item)
    payload['answers'] = answers
    return payload


def latest_response_for_task(conn, task_id: int):
    row = conn.execute(
        "SELECT id FROM survey_responses WHERE task_id=? ORDER BY submitted_at DESC,id DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    return response_detail(conn, row['id']) if row else None


def responses_for_survey(conn, survey_id: int):
    rows = conn.execute(
        """
        SELECT sr.id
        FROM survey_responses sr
        JOIN survey_tasks t ON t.id=sr.task_id
        WHERE t.survey_id=?
        ORDER BY sr.submitted_at DESC,sr.id DESC
        """,
        (survey_id,),
    ).fetchall()
    return [response_detail(conn, r['id']) for r in rows]
