from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from . import db
from .deps import get_db_path, SESSIONS, auth_user
from .security import hash_pin, new_token, verify_pin

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    login_code: str
    pin: str


class ChangePinRequest(BaseModel):
    current_pin: str
    new_pin: str


def _login(payload: LoginRequest, expected_role: str, db_path, request: Request):
    conn = db.connect(db_path)
    row = conn.execute("SELECT * FROM users WHERE login_code=?", (payload.login_code.strip(),)).fetchone()
    if not row or row["status"] != "active" or row["role"] != expected_role or not verify_pin(payload.pin, row["pin_hash"]):
        raise HTTPException(status_code=401, detail="Invalid login code or PIN")
    token = new_token()
    ttl = getattr(request.app.state, "session_ttl_seconds", 12 * 60 * 60)
    now = time.time()
    SESSIONS[token] = {"user_id": row["id"], "role": row["role"], "created_at": now, "expires_at": now + ttl}
    conn.execute("UPDATE users SET last_login_at=CURRENT_TIMESTAMP WHERE id=?", (row["id"],))
    conn.commit()
    return {"token": token, "user": {"id": row["id"], "login_code": row["login_code"], "name": row["name"], "role": row["role"], "region": row["region"]}}


@router.post("/as-login")
def as_login(payload: LoginRequest, request: Request, db_path=Depends(get_db_path)):
    return _login(payload, "as", db_path, request)


@router.post("/admin-login")
def admin_login(payload: LoginRequest, request: Request, db_path=Depends(get_db_path)):
    return _login(payload, "super_admin", db_path, request)


@router.post("/change-pin")
def change_pin(payload: ChangePinRequest, user: dict = Depends(auth_user), db_path=Depends(get_db_path)):
    new_pin = str(payload.new_pin or "").strip()
    if len(new_pin) < 6 or not new_pin.isdigit():
        raise HTTPException(status_code=400, detail="New PIN must be at least 6 digits")
    conn = db.connect(db_path)
    row = conn.execute("SELECT id,pin_hash FROM users WHERE id=?", (user["id"],)).fetchone()
    if not row or not verify_pin(payload.current_pin, row["pin_hash"]):
        raise HTTPException(status_code=400, detail="Current PIN is incorrect")
    conn.execute("UPDATE users SET pin_hash=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (hash_pin(new_pin), user["id"]))
    conn.commit()
    return {"ok": True}
