from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User
from app.ratelimit import check_rate
from app.schemas import LoginIn, RegisterIn
from app.security import (create_session, destroy_session, get_optional_user, hash_password, verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# constant-time-ish defence against user enumeration via timing
_DUMMY_HASH = hash_password("not-a-real-password-placeholder")


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "display_name": u.display_name, "role": u.role,
            "created_at": u.created_at.isoformat() if u.created_at else None}


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    check_rate(request, "auth", get_settings().rate_auth_per_min)
    if db.scalar(select(User.id).where(User.email == body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "อีเมลนี้ถูกใช้สมัครแล้ว")
    user = User(email=body.email, display_name=body.display_name, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    create_session(db, user, response)
    return user_out(user)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    check_rate(request, "auth", get_settings().rate_auth_per_min)
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    ok = verify_password(user.password_hash if user else _DUMMY_HASH, body.password)
    if not user or not ok or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "อีเมลหรือรหัสผ่านไม่ถูกต้อง")
    create_session(db, user, response)
    return user_out(user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    destroy_session(db, request, response)
    response.status_code = 204
    return response


@router.get("/me")
def me(user: User | None = Depends(get_optional_user)):
    return {"user": user_out(user) if user else None}
