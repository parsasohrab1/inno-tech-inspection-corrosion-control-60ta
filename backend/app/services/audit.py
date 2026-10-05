"""Audit Trail غیرقابل تغییر: زنجیره هش SHA-256 + تریگر ممنوعیت UPDATE/DELETE."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone


def _hash(prev: str, ts: str, user: str, action: str, entity: str, eid: str, detail: str) -> str:
    return hashlib.sha256("|".join([prev or "", ts, user or "", action, entity or "", eid or "", detail or ""]).encode()).hexdigest()


def log(conn: sqlite3.Connection, user: str | None, action: str, entity: str = "", entity_id: str = "",
        detail: dict | str | None = None, commit: bool = True) -> None:
    d = detail if isinstance(detail, str) else json.dumps(detail or {}, ensure_ascii=False)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = conn.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    prev = row[0] if row else ""
    conn.execute("INSERT INTO audit_log(ts,username,action,entity,entity_id,detail,prev_hash,hash) VALUES(?,?,?,?,?,?,?,?)",
                 (ts, user, action, entity, entity_id, d, prev, _hash(prev, ts, user or "", action, entity, entity_id, d)))
    if commit:
        conn.commit()


def verify(conn: sqlite3.Connection) -> dict:
    prev, n = "", 0
    for r in conn.execute("SELECT * FROM audit_log ORDER BY id"):
        exp = _hash(prev, r["ts"], r["username"] or "", r["action"], r["entity"], r["entity_id"], r["detail"])
        if r["prev_hash"] != prev or r["hash"] != exp:
            return {"valid": False, "broken_at_id": r["id"], "checked": n}
        prev, n = r["hash"], n + 1
    return {"valid": True, "checked": n}
