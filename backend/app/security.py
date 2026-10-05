"""JWT + RBAC."""
from __future__ import annotations

import sqlite3
import time

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config
from .db import get_conn, one

ROLES = {
    "admin": "مدیر سیستم", "manager": "مدیر بازرسی و تعمیرات", "asset": "مدیر دارایی",
    "inspector": "بازرس فنی", "ndt": "کارشناس NDT", "corrosion": "مهندس خوردگی",
    "rbi": "کارشناس RBI", "hse": "مدیر HSE",
}
bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str, rounds: int = 12) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds)).decode()


def verify_password(pw: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user: dict) -> str:
    now = int(time.time())
    return jwt.encode({"sub": user["username"], "role": user["role"], "iat": now,
                       "exp": now + config.TOKEN_TTL_MINUTES * 60}, config.SECRET_KEY, algorithm="HS256")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer),
                 conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "احراز هویت لازم است")
    try:
        payload = jwt.decode(cred.credentials, config.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن نامعتبر یا منقضی است")
    u = one(conn, "SELECT user_id,username,full_name,role,is_active FROM users WHERE username=?", (payload["sub"],))
    if not u or not u["is_active"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "کاربر غیرفعال است")
    return u


def require(*roles: str):
    """admin همیشه مجاز است."""
    allowed = set(roles) | {"admin"}

    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی کافی برای این عملیات ندارید")
        return user

    return dep
