from __future__ import annotations

from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "as_survey.db"
SCHEMA_PATH = ROOT / "schema.sql"


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    # 60-user pilot tuning: wait briefly instead of failing immediately on
    # concurrent writes, and use WAL so readers do not block writers.
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}
