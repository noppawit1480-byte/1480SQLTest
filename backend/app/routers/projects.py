from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Exercise, Project, User
from app.security import get_optional_user
from app.services import progress

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
def list_projects(db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    pp = progress.project_progress(db, user.id if user else None)
    out = []
    for p in db.scalars(select(Project).order_by(Project.position)):
        prog = pp.get(p.id, {"total": 0, "solved": 0})
        out.append({"slug": p.slug, "title": p.title, "role": p.role, "summary": p.summary, "sample_db": p.sample_db,
                    "difficulty": p.difficulty, "tasks": prog["total"], "solved": prog["solved"],
                    "completed": bool(prog["total"]) and prog["solved"] == prog["total"]})
    return out


@router.get("/{slug}")
def get_project(slug: str, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    p = db.scalar(select(Project).where(Project.slug == slug))
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบโปรเจกต์")
    solved = progress.solved_exercise_ids(db, user.id) if user else set()
    attempted = progress.attempted_exercise_ids(db, user.id) if user else set()
    tasks = list(db.scalars(select(Exercise).where(Exercise.project_id == p.id).order_by(Exercise.position)))
    items = [{"code": t.code, "title": t.title, "difficulty": t.difficulty, "category": t.category, "points": t.points,
              "status": "solved" if t.id in solved else "attempted" if t.id in attempted else "new"} for t in tasks]
    n_solved = sum(1 for t in items if t["status"] == "solved")
    return {"slug": p.slug, "title": p.title, "role": p.role, "summary": p.summary, "brief_md": p.brief_md,
            "deliverables": p.deliverables, "sample_db": p.sample_db, "difficulty": p.difficulty, "tasks": items,
            "solved": n_solved, "completed": bool(items) and n_solved == len(items),
            "points_total": sum(t["points"] for t in items),
            "points_earned": sum(t["points"] for t in items if t["status"] == "solved")}
