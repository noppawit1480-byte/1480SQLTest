"""Password hashing, server-side sessions and RBAC dependencies."""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User, UserSession

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User, response: Response) -> None:
    s = get_settings()
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(days=s.session_ttl_days)
    db.add(UserSession(token_hash=_token_hash(token), user_id=user.id, expires_at=expires))
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at < datetime.now(UTC)))
    db.commit()
    response.set_cookie(s.session_cookie_name, token, max_age=s.session_ttl_days * 86400, httponly=True,
                        secure=s.cookie_secure, samesite="lax", path="/")


def destroy_session(db: Session, request: Request, response: Response) -> None:
    s = get_settings()
    token = request.cookies.get(s.session_cookie_name)
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == _token_hash(token)))
        db.commit()
    response.delete_cookie(s.session_cookie_name, path="/")


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token or len(token) > 200:
        return None
    row = db.execute(select(UserSession).where(UserSession.token_hash == _token_hash(token))).scalar_one_or_none()
    if row is None or row.expires_at < datetime.now(UTC):
        return None
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        return None
    request.state.user_id = user.id
    return user


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "กรุณาเข้าสู่ระบบ")
    return user


def require_role(*roles: str):
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "ไม่มีสิทธิ์เข้าถึง")
        return user
    return dep
