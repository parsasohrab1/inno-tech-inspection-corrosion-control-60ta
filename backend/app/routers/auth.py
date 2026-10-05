import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import get_conn, one, rows
from ..security import ROLES, create_token, current_user, require, verify_password
from ..services import audit

router = APIRouter(prefix="/api", tags=["auth"])
_fails: dict[str, list[float]] = {}


class Login(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: Login, conn: sqlite3.Connection = Depends(get_conn)):
    import time
    now = time.time()
    recent = [t for t in _fails.get(body.username, []) if now - t < 300]
    if len(recent) >= 5:
        raise HTTPException(429, "تعداد تلاش ناموفق زیاد است؛ ۵ دقیقه بعد دوباره تلاش کنید")
    u = one(conn, "SELECT * FROM users WHERE username=?", (body.username,))
    if not u or not u["is_active"] or not verify_password(body.password, u["password_hash"]):
        _fails[body.username] = recent + [now]
        audit.log(conn, body.username, "login_failed", "user", body.username)
        raise HTTPException(401, "نام کاربری یا گذرواژه نادرست است")
    _fails.pop(body.username, None)
    audit.log(conn, u["username"], "login", "user", u["username"])
    return {"access_token": create_token(u), "token_type": "bearer",
            "user": {"username": u["username"], "full_name": u["full_name"], "role": u["role"], "role_fa": ROLES.get(u["role"])}}


@router.get("/auth/me")
def me(user: dict = Depends(current_user)):
    return {**user, "role_fa": ROLES.get(user["role"])}


@router.get("/users")
def users(conn: sqlite3.Connection = Depends(get_conn), _=Depends(require())):
    return rows(conn, "SELECT user_id,username,full_name,role,is_active FROM users WHERE password_hash IS NOT NULL ORDER BY user_id")


@router.get("/audit")
def audit_list(limit: int = 100, action: str | None = None, entity_id: str | None = None,
               conn: sqlite3.Connection = Depends(get_conn), _=Depends(require("manager", "hse"))):
    sql, p = "SELECT id,ts,username,action,entity,entity_id,detail,hash FROM audit_log WHERE 1=1", []
    if action:
        sql += " AND action=?"; p.append(action)
    if entity_id:
        sql += " AND entity_id=?"; p.append(entity_id)
    return rows(conn, sql + " ORDER BY id DESC LIMIT ?", p + [min(limit, 1000)])


@router.get("/audit/verify")
def audit_verify(conn: sqlite3.Connection = Depends(get_conn), _=Depends(require("manager", "hse"))):
    return audit.verify(conn)
