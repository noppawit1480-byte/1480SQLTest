"""CSV import into the learner's writable sandbox (Phase 3)."""
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import SampleDatabase, User
from app.ratelimit import check_rate
from app.security import get_current_user
from app.services import csv_import
from app.services.sandbox.sqlite_engine import get_engine

router = APIRouter(prefix="/api/csv", tags=["csv"])
MAX_CHARS = csv_import.MAX_BYTES  # pydantic limit on characters; bytes are re-checked in parse()


class PreviewIn(BaseModel):
    csv_text: str = Field(min_length=1, max_length=MAX_CHARS)
    delimiter: str = ","
    has_header: bool = True


class ColumnIn(BaseModel):
    name: str = Field(pattern=r"^[a-z_][a-z0-9_]{0,62}$")
    type: Literal[csv_import.TYPES]  # type: ignore[valid-type]


class ImportIn(PreviewIn):
    db_key: str = Field(default="blank", pattern=r"^[a-z][a-z0-9_]{1,30}$")
    engine: Literal["postgresql", "sqlite", "mysql"] = "postgresql"
    table_name: str = Field(pattern=r"^[a-z_][a-z0-9_]{0,62}$")
    columns: list[ColumnIn] | None = None
    replace: bool = False


@router.post("/preview")
def preview(body: PreviewIn, user: User = Depends(get_current_user)):
    try:
        return csv_import.preview(body.csv_text, body.delimiter, body.has_header)
    except csv_import.CsvError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None


@router.post("/import")
def do_import(body: ImportIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    check_rate(request, "csv_import", 10)
    if db.get(SampleDatabase, body.db_key) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบฐานข้อมูลนี้")
    try:
        names, data = csv_import.parse(body.csv_text, body.delimiter, body.has_header)
        if body.columns:
            if len(body.columns) != len(names):
                raise csv_import.CsvError("จำนวนคอลัมน์ที่กำหนดไม่ตรงกับไฟล์")
            columns = [c.model_dump() for c in body.columns]
        else:
            columns = [{"name": n, "type": csv_import.infer_type([r[i] for r in data])} for i, n in enumerate(names)]
        eng = get_engine(body.engine)
        target = eng.ensure_user_db(user.id, body.db_key)
        if body.engine == "postgresql":
            n = csv_import.import_postgres(eng, target, body.table_name, columns, data, body.replace)
        elif body.engine == "mysql":
            n = csv_import.import_mysql(eng, target, body.table_name, columns, data, body.replace)
            if eng.user_db_size(user.id, body.db_key) > get_settings().writable_db_max_bytes:
                eng.reset_user_db(user.id, body.db_key)
                raise csv_import.CsvError("ฐานข้อมูลส่วนตัวเกินขนาดที่กำหนด จึงถูกรีเซ็ต")
        else:
            n = csv_import.import_sqlite(target.database, body.table_name, columns, data, body.replace)
            if os.path.getsize(target.database) > get_settings().writable_db_max_bytes:
                eng.reset_user_db(user.id, body.db_key)
                raise csv_import.CsvError("ฐานข้อมูลส่วนตัวเกินขนาดที่กำหนด จึงถูกรีเซ็ต")
    except csv_import.CsvError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    return {"ok": True, "table": body.table_name, "rows": n, "columns": columns, "db_key": body.db_key, "engine": body.engine,
            "message": f"นำเข้า {n:,} แถวไปที่ตาราง {body.table_name} ({body.db_key}, {body.engine}, Writable sandbox) แล้ว"}
