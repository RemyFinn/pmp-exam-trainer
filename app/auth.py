from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
from fastapi import Cookie, Depends, HTTPException, Response

from .db import transaction


SESSION_COOKIE = "pmp_session"
SESSION_DAYS = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_secret() -> str:
    secret = os.getenv("SESSION_SECRET")
    if not secret:
        raise RuntimeError("SESSION_SECRET is required.")
    return secret


def sign_token(token: str) -> str:
    signature = hmac.new(session_secret().encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{token}.{signature}"


def unsign_token(signed: str) -> str | None:
    if "." not in signed:
        return None
    token, signature = signed.rsplit(".", 1)
    expected = hmac.new(session_secret().encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    return token


def cookie_secure() -> bool:
    return os.getenv("COOKIE_SECURE", "0").lower() in {"1", "true", "yes"}


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        sign_token(token),
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=SESSION_DAYS)
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO auth_sessions (user_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            (user_id, hash_token(token), expires_at),
        )
    return token


def create_initial_admin() -> None:
    username = os.getenv("FIRST_ADMIN_USERNAME")
    password = os.getenv("FIRST_ADMIN_PASSWORD")
    if not username or not password:
        return
    display_name = os.getenv("FIRST_ADMIN_DISPLAY_NAME", username)
    with transaction() as conn:
        exists = conn.execute("SELECT id FROM users WHERE username = %s", (username,)).fetchone()
        if exists:
            return
        conn.execute(
            """
            INSERT INTO users (username, display_name, password_hash, role, is_active)
            VALUES (%s, %s, %s, 'admin', 1)
            """,
            (username, display_name, hash_password(password)),
        )


def current_user(session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None) -> dict:
    if not session:
        raise HTTPException(status_code=401, detail="请先登录")
    token = unsign_token(session)
    if not token:
        raise HTTPException(status_code=401, detail="登录已失效")
    with transaction() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.username, u.display_name, u.role, u.is_active
            FROM auth_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = %s AND s.expires_at > CURRENT_TIMESTAMP
            """,
            (hash_token(token),),
        ).fetchone()
    if row is None or not row["is_active"]:
        raise HTTPException(status_code=401, detail="登录已失效")
    return dict(row)


def current_session_token(session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None) -> str | None:
    if not session:
        return None
    return unsign_token(session)


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
