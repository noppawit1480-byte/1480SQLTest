"""ER Diagram Builder / Database Design Playground (Phase 3)."""
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ErDesign, SampleDatabase, User
from app.ratelimit import check_rate
from app.routers.playground import er_mermaid, readonly_schema
from app.security import get_current_user
from app.services import er_design
from app.services.sandbox.sqlite_engine import get_engine

router = APIRouter(prefix="/api/designs", tags=["designs"])


class DesignBody(BaseModel):
    tables: list[dict] = Field(default_factory=list, max_length=er_design.MAX_TABLES)
    relations: list[dict] = Field(default_factory=list, max_length=200)


class DesignIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    design: DesignBody


class ApplyIn(BaseModel):
    engine: Literal["postgresql", "sqlite", "mysql"] = "postgresql"


def _check(design: DesignBody) -> dict:
    d = design.model_dump()
    return {"issues": [i.__dict__ for i in er_design.validate(d)], "mermaid": er_design.mermaid(d)}


@router.post("/ddl")
def ddl(body: DesignBody):
    """Stateless: validate + DDL for each dialect + Mermaid preview."""
    out = _check(body)
    if any(i["level"] == "error" for i in out["issues"]):
        out["ddl"] = None
    else:
        out["ddl"] = {d: er_design.generate_ddl(body.model_dump(), d) for d in ("postgresql", "sqlite", "mysql")}
    return out


@router.get("/from-db/{key}")
def from_db(key: str, db: Session = Depends(get_db)):
    if db.get(SampleDatabase, key) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบฐานข้อมูลนี้")
    return er_design.from_schema(readonly_schema(key))


def _out(d: ErDesign) -> dict:
    return {"id": d.id, "name": d.name, "design": d.design, "updated_at": d.updated_at.isoformat()}


def _own(db: Session, user: User, did: int) -> ErDesign:
    d = db.get(ErDesign, did)
    if d is None or d.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบแบบ ER")
    return d


@router.get("")
def list_designs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [_out(d) for d in db.scalars(select(ErDesign).where(ErDesign.user_id == user.id).order_by(ErDesign.updated_at.desc()))]


@router.post("", status_code=201)
def create_design(body: DesignIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = ErDesign(user_id=user.id, name=body.name.strip(), design=body.design.model_dump())
    db.add(d)
    db.commit()
    return _out(d)


@router.get("/{did}")
def get_design(did: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _out(_own(db, user, did))


@router.put("/{did}")
def update_design(did: int, body: DesignIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = _own(db, user, did)
    d.name, d.design, d.updated_at = body.name.strip(), body.design.model_dump(), datetime.now(UTC)
    db.commit()
    return _out(d)


@router.delete("/{did}", status_code=204)
def delete_design(did: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(_own(db, user, did))
    db.commit()


@router.post("/{did}/apply")
def apply_design(did: int, body: ApplyIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Reset the learner's writable `blank` DB and create the designed tables in it."""
    check_rate(request, "reset", 10)
    d = _own(db, user, did)
    try:
        ddl_text = er_design.generate_ddl(d.design, body.engine)
    except er_design.DesignError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "แบบยังมีข้อผิดพลาด: " + "; ".join(e.issues)) from None
    eng = get_engine(body.engine)
    eng.reset_user_db(user.id, "blank")
    target = eng.ensure_user_db(user.id, "blank")
    res = eng.execute(target, ddl_text)
    if not res.ok:
        return {"ok": False, "error": res.error.message if res.error else "", "ddl": ddl_text}
    from dataclasses import asdict
    tables = [asdict(t) for t in eng.introspect(target)]
    return {"ok": True, "ddl": ddl_text, "db_key": "blank", "engine": body.engine, "tables": [t["name"] for t in tables],
            "er_mermaid": er_mermaid(tables),
            "message": f"สร้าง {len(tables)} ตารางในฐานข้อมูล blank (Writable sandbox) แล้ว — เปิด Playground โหมด Writable เพื่อเพิ่มข้อมูลและ query"}
