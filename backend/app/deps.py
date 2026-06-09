from __future__ import annotations

import time
from pathlib import Path
from fastapi import Depends, Header, HTTPException, Request

from . import db

SESSIONS: dict[str, dict] = {}


def get_db_path(request: Request) -> Path:
    return request.app.state.db_path


def auth_user(request: Request, authorization: str | None = Header(default=None), db_path: Path = Depends(get_db_path)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    session = SESSIONS.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    if session.get("expires_at") is not None and time.time() > session["expires_at"]:
        SESSIONS.pop(token, None)
        raise HTTPException(status_code=401, detail="Session expired")
    conn = db.connect(db_path)
    row = conn.execute("SELECT * FROM users WHERE id=? AND status='active'", (session["user_id"],)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Inactive or missing user")
    return db.row_to_dict(row)


def require_admin(user: dict = Depends(auth_user)) -> dict:
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def require_as(user: dict = Depends(auth_user)) -> dict:
    if user["role"] != "as":
        raise HTTPException(status_code=403, detail="AS only")
    return user
