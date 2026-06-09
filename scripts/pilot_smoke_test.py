#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request


@dataclass
class SmokeResult:
    login_code: str
    ok: bool
    task_count: int = 0
    active_surveys: int = 0
    completed_surveys: int = 0
    error: str = ""


def _json_request(url: str, method: str = "GET", payload: dict | None = None, token: str | None = None, timeout: int = 10) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url, data=data, headers=headers, method=method)
    with request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


def read_users(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    required = {"login_code", "pin"}
    if not rows:
        raise SystemExit("users CSV is empty")
    if not required.issubset(rows[0].keys()):
        raise SystemExit("users CSV must have columns: login_code,pin")
    users = []
    for row in rows:
        login_code = (row.get("login_code") or "").strip().upper()
        pin = (row.get("pin") or "").strip()
        if not login_code or not pin:
            users.append({"login_code": login_code or "<blank>", "pin": pin, "invalid": "missing login_code or pin"})
        else:
            users.append({"login_code": login_code, "pin": pin})
    return users


def smoke_user(base_url: str, user: dict[str, str]) -> SmokeResult:
    login_code = user["login_code"]
    if user.get("invalid"):
        return SmokeResult(login_code=login_code, ok=False, error=user["invalid"])
    try:
        auth = _json_request(
            f"{base_url}/api/auth/as-login",
            method="POST",
            payload={"login_code": login_code, "pin": user["pin"]},
        )
        token = auth["token"]
        tasks = _json_request(f"{base_url}/api/as/tasks", token=token)
        active = tasks.get("active_surveys") or []
        completed = tasks.get("completed_surveys") or []
        task_count = sum(len(s.get("tasks") or []) for s in active + completed)
        return SmokeResult(
            login_code=login_code,
            ok=True,
            task_count=task_count,
            active_surveys=len(active),
            completed_surveys=len(completed),
        )
    except error.HTTPError as exc:
        # Never print the user's PIN.
        try:
            body = exc.read().decode("utf-8")[:180]
        except Exception:
            body = ""
        return SmokeResult(login_code=login_code, ok=False, error=f"HTTP {exc.code} {body}")
    except Exception as exc:
        return SmokeResult(login_code=login_code, ok=False, error=str(exc)[:180])


def main() -> int:
    parser = argparse.ArgumentParser(description="AS Survey pilot smoke test: health, AS login, AS tasks. Does not print PINs.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8030", help="Backend root, without /api")
    parser.add_argument("--users-csv", required=True, type=Path, help="CSV with columns login_code,pin")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--limit", type=int, default=0, help="Limit number of users for a quick sample; 0 = all")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    started = time.time()
    health = _json_request(f"{base_url}/health")
    if not health.get("ok"):
        print(json.dumps({"ok": False, "stage": "health", "health": health}, ensure_ascii=False))
        return 2

    users = read_users(args.users_csv)
    if args.limit:
        users = users[: args.limit]

    results: list[SmokeResult] = []
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = [pool.submit(smoke_user, base_url, user) for user in users]
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda r: r.login_code)
    failures = [r for r in results if not r.ok]
    summary = {
        "ok": not failures,
        "checked_users": len(results),
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "duration_seconds": round(time.time() - started, 2),
        "min_task_count": min((r.task_count for r in results if r.ok), default=0),
        "max_task_count": max((r.task_count for r in results if r.ok), default=0),
        "failures": [{"login_code": r.login_code, "error": r.error} for r in failures[:20]],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
