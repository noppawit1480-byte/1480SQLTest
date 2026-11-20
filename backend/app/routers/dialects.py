from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import SampleDatabase
from app.ratelimit import check_rate
from app.services import dialects
from app.services.sandbox.sqlite_engine import get_engine

router = APIRouter(prefix="/api/dialects", tags=["dialects"])


class CompareIn(BaseModel):
    sql: str = Field(min_length=1, max_length=20000)
    db_key: str = Field(default="ecommerce", pattern=r"^[a-z][a-z0-9_]{1,30}$")


@router.get("/reference")
def reference():
    return {"engines": ["postgresql", "sqlite", "mysql", "sqlserver"], "executable": ["postgresql", "sqlite"],
            "features": [asdict(f) for f in dialects.FEATURES.values()]}


@router.post("/compare")
def compare(body: CompareIn, request: Request, db: Session = Depends(get_db)):
    check_rate(request, "execute", get_settings().rate_execute_per_min)
    if db.get(SampleDatabase, body.db_key) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบฐานข้อมูลนี้")
    pg, sq = get_engine("postgresql"), get_engine("sqlite")
    pg_res = pg.execute(pg.readonly_target(body.db_key), body.sql)
    sq_res = sq.execute(sq.readonly_target(body.db_key), body.sql)
    keys = dialects.detect_features(body.sql)
    return {"postgresql": asdict(pg_res), "sqlite": asdict(sq_res), "comparison": dialects.compare(body.sql, pg_res, sq_res),
            "features": [asdict(dialects.FEATURES[k]) for k in keys]}
