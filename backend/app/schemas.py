"""Pydantic request models (backend validation). Responses are documented in docs/API.md."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DbKey = Field(pattern=r"^[a-z][a-z0-9_]{1,30}$")


class RegisterIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("รูปแบบอีเมลไม่ถูกต้อง")
        return v

    @field_validator("display_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("กรุณากรอกชื่อที่แสดง")
        return v


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


Engine = Literal["postgresql", "sqlite", "mysql"]


class ExecuteIn(BaseModel):
    db_key: str = DbKey
    engine: Engine = "postgresql"
    mode: Literal["readonly", "writable"] = "readonly"
    sql: str = Field(max_length=20000)


class ValidateIn(BaseModel):
    sql: str = Field(max_length=20000)


class ResetIn(BaseModel):
    db_key: str = DbKey
    engine: Engine = "postgresql"


class SqlIn(BaseModel):
    sql: str = Field(max_length=20000)


class SavedQueryIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    db_key: str = DbKey
    engine: Engine = "postgresql"
    sql: str = Field(min_length=1, max_length=20000)


class LessonProgressIn(BaseModel):
    status: Literal["in_progress", "completed"]


class NoteIn(BaseModel):
    body: str = Field(max_length=10000)


class HeartbeatIn(BaseModel):
    seconds: int = Field(ge=1, le=60)
