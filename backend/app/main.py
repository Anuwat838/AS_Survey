from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db
from .routes_admin import router as admin_router
from .routes_as import router as as_router
from .routes_auth import router as auth_router
from .routes_import import router as import_router


def _origins_from_env() -> list[str]:
    raw = os.getenv("AS_SURVEY_ALLOWED_ORIGINS", "http://localhost:8021,http://127.0.0.1:8021")
    return [item.strip() for item in raw.split(",") if item.strip()]


def create_app(db_path=db.DB_PATH, session_ttl_seconds: int | None = None, allowed_origins: list[str] | None = None) -> FastAPI:
    app = FastAPI(title="AS Survey Backend MVP")
    app.state.db_path = db_path
    app.state.session_ttl_seconds = session_ttl_seconds or int(os.getenv("AS_SURVEY_SESSION_TTL_SECONDS", str(12 * 60 * 60)))
    origins = allowed_origins if allowed_origins is not None else _origins_from_env()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(as_router)
    app.include_router(admin_router)
    app.include_router(import_router)
    upload_dir = Path(db_path).parent / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


app = create_app()
