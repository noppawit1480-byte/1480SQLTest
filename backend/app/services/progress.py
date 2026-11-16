"""Progress tracking, levels, streaks and achievements — all computed from real stored events."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, distinct, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (Achievement, ActivityDay, Course, Exercise, Lesson, LessonProgress, Project, QueryHistory,
                        Submission, UserAchievement)

LEVELS = [(0, "Novice"), (50, "Beginner"), (250, "Intermediate"), (600, "Advanced"), (1000, "Professional")]

ACHIEVEMENTS = [
    ("first_query", "First Query", "รัน SQL สำเร็จเป็นครั้งแรก", "play"),
    ("first_correct", "First Blood", "ตอบโจทย์ถูกเป็นข้อแรก", "check"),
    ("sql_beginner", "SQL Beginner", "ทำโจทย์ระดับ Easy ถูก 10 ข้อ", "sprout"),
    ("beginner_graduate", "Beginner Graduate", "เรียนจบหลักสูตร Beginner ครบทุกบท", "graduation"),
    ("join_master", "JOIN Master", "ทำโจทย์หมวด JOIN ถูก 5 ข้อ", "link"),
    ("subquery_expert", "Subquery Expert", "ทำโจทย์หมวด Subquery/CTE ถูก 4 ข้อ", "layers"),
    ("window_master", "Window Function Master", "ทำโจทย์หมวด Window Functions ถูก 4 ข้อ", "window"),
    ("data_builder", "Data Builder", "ทำโจทย์ DML/DDL ถูก 3 ข้อ", "hammer"),
    ("streak_7", "7-Day Streak", "เรียนต่อเนื่อง 7 วัน", "flame"),
    ("sql_professional", "SQL Professional", "สะสมคะแนนถึงระดับ Professional (1,000 คะแนน)", "trophy"),
    ("real_world_analyst", "Real-World Analyst", "ทำ Real-World Project สำเร็จครบทุกงาน 1 โปรเจกต์", "briefcase"),
    ("project_master", "Project Master", "ทำ Real-World Projects สำเร็จครบทุกโปรเจกต์", "crown"),
]


def today_local() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


def level_for(points: int) -> dict:
    current = LEVELS[0]
    nxt = None
    for i, (threshold, name) in enumerate(LEVELS):
        if points >= threshold:
            current = (threshold, name)
            nxt = LEVELS[i + 1] if i + 1 < len(LEVELS) else None
    return {"name": current[1], "points": points, "current_threshold": current[0],
            "next_name": nxt[1] if nxt else None, "next_threshold": nxt[0] if nxt else None}


def record_activity(db: Session, user_id: int, seconds: int = 0, events: int = 1) -> None:
    stmt = pg_insert(ActivityDay).values(user_id=user_id, day=today_local(), seconds=seconds, events=events)
    stmt = stmt.on_conflict_do_update(index_elements=[ActivityDay.user_id, ActivityDay.day],
                                      set_={"seconds": ActivityDay.seconds + seconds, "events": ActivityDay.events + events})
    db.execute(stmt)


def compute_streak(days: list[date], today: date) -> int:
    s = set(days)
    cur = today if today in s else today - timedelta(days=1)
    streak = 0
    while cur in s:
        streak += 1
        cur -= timedelta(days=1)
    return streak


def user_points(db: Session, user_id: int) -> int:
    solved = select(Submission.exercise_id).distinct().where(Submission.user_id == user_id, Submission.is_correct)
    return int(db.scalar(select(func.coalesce(func.sum(Exercise.points), 0)).where(Exercise.id.in_(solved))) or 0)


def solved_counts_by(db: Session, user_id: int, column) -> dict[str, int]:
    solved = select(Submission.exercise_id).distinct().where(Submission.user_id == user_id, Submission.is_correct)
    rows = db.execute(select(column, func.count()).where(Exercise.id.in_(solved)).group_by(column)).all()
    return {k: int(v) for k, v in rows}


def project_progress(db: Session, user_id: int | None) -> dict[int, dict]:
    """{project_id: {"total": n_tasks, "solved": n_solved}} for every project."""
    rows = db.execute(select(Project.id, func.count(Exercise.id)).join(Exercise, Exercise.project_id == Project.id)
                      .group_by(Project.id)).all()
    out = {pid: {"total": int(n), "solved": 0} for pid, n in rows}
    if user_id is not None:
        solved = select(Submission.exercise_id).distinct().where(Submission.user_id == user_id, Submission.is_correct)
        for pid, n in db.execute(select(Exercise.project_id, func.count()).where(Exercise.project_id.is_not(None),
                                                                                  Exercise.id.in_(solved))
                                 .group_by(Exercise.project_id)).all():
            out.setdefault(pid, {"total": 0, "solved": 0})["solved"] = int(n)
    return out


def evaluate_achievements(db: Session, user_id: int) -> list[str]:
    """Award any newly-earned achievements. Returns keys of newly awarded ones."""
    have = set(db.scalars(select(UserAchievement.achievement_key).where(UserAchievement.user_id == user_id)))
    by_diff = solved_counts_by(db, user_id, Exercise.difficulty)
    by_cat = solved_counts_by(db, user_id, Exercise.category)
    by_type = solved_counts_by(db, user_id, Exercise.check_type)
    total_correct = sum(by_diff.values())
    ran_query = db.scalar(select(func.count()).select_from(QueryHistory).where(QueryHistory.user_id == user_id,
                                                                              QueryHistory.success)) or 0
    beginner_total = db.scalar(select(func.count()).select_from(Lesson).join(Course).where(Course.level == "beginner")) or 0
    beginner_done = db.scalar(select(func.count()).select_from(LessonProgress).join(Lesson).join(Course).where(
        LessonProgress.user_id == user_id, LessonProgress.status == "completed", Course.level == "beginner")) or 0
    days = list(db.scalars(select(ActivityDay.day).where(ActivityDay.user_id == user_id)))
    proj = project_progress(db, user_id)
    done_projects = sum(1 for p in proj.values() if p["total"] and p["solved"] == p["total"])
    checks = {
        "first_query": ran_query > 0 or total_correct > 0,
        "first_correct": total_correct >= 1,
        "sql_beginner": by_diff.get("easy", 0) >= 10,
        "beginner_graduate": beginner_total > 0 and beginner_done >= beginner_total,
        "join_master": by_cat.get("JOIN", 0) >= 5,
        "subquery_expert": by_cat.get("Subquery", 0) + by_cat.get("CTE", 0) >= 4,
        "window_master": by_cat.get("Window Functions", 0) >= 4,
        "data_builder": by_type.get("dml", 0) >= 3,
        "streak_7": compute_streak(days, today_local()) >= 7,
        "sql_professional": user_points(db, user_id) >= 1000,
        "real_world_analyst": done_projects >= 1,
        "project_master": bool(proj) and done_projects == len(proj),
    }
    new = [k for k, ok in checks.items() if ok and k not in have]
    for k in new:
        db.add(UserAchievement(user_id=user_id, achievement_key=k))
    return new


def dashboard(db: Session, user_id: int) -> dict:
    total_lessons = db.scalar(select(func.count()).select_from(Lesson)) or 0
    done_lessons = db.scalar(select(func.count()).select_from(LessonProgress).where(
        LessonProgress.user_id == user_id, LessonProgress.status == "completed")) or 0
    total_ex = db.scalar(select(func.count()).select_from(Exercise).where(Exercise.project_id.is_(None))) or 0
    solved = db.scalar(select(func.count(distinct(Submission.exercise_id))).join(Exercise, Exercise.id == Submission.exercise_id)
                       .where(Submission.user_id == user_id, Submission.is_correct, Exercise.project_id.is_(None))) or 0
    pp = project_progress(db, user_id)
    projects_done = sum(1 for p in pp.values() if p["total"] and p["solved"] == p["total"])
    subs, correct = db.execute(select(func.count(), func.count().filter(Submission.is_correct)).where(
        Submission.user_id == user_id)).one()
    accuracy = round(100 * correct / subs, 1) if subs else None

    act = db.execute(select(ActivityDay.day, ActivityDay.seconds).where(ActivityDay.user_id == user_id)).all()
    today = today_local()
    streak = compute_streak([d for d, _ in act], today)
    total_seconds = sum(s for _, s in act)

    # course progress
    course_rows = db.execute(
        select(Course.slug, Course.title, Course.level, func.count(Lesson.id),
               func.count(LessonProgress.lesson_id).filter(LessonProgress.status == "completed"))
        .join(Lesson, Lesson.course_id == Course.id)
        .outerjoin(LessonProgress, and_(LessonProgress.lesson_id == Lesson.id, LessonProgress.user_id == user_id))
        .group_by(Course.id).order_by(Course.position)).all()
    courses = [{"slug": s, "title": t, "level": lv, "total": n, "completed": c,
                "percent": round(100 * c / n) if n else 0} for s, t, lv, n, c in course_rows]

    # skill progress by exercise category
    cat_total = dict(db.execute(select(Exercise.category, func.count()).group_by(Exercise.category)).all())
    cat_done = solved_counts_by(db, user_id, Exercise.category)
    skills = [{"category": c, "solved": cat_done.get(c, 0), "total": n,
               "percent": round(100 * cat_done.get(c, 0) / n)} for c, n in sorted(cat_total.items())]

    # recent submissions (latest per exercise)
    recent = db.execute(
        select(Exercise.code, Exercise.title, Exercise.difficulty, Submission.is_correct, Submission.created_at)
        .join(Exercise, Exercise.id == Submission.exercise_id).where(Submission.user_id == user_id)
        .order_by(Submission.created_at.desc()).limit(6)).all()
    recent_ex = [{"code": c, "title": t, "difficulty": d, "is_correct": ok, "at": at.isoformat()} for c, t, d, ok, at in recent]

    # continue learning: most recently touched in-progress lesson, else next not-completed lesson
    cur = db.execute(select(Lesson.slug, Lesson.title, Course.slug).join(Course)
                     .join(LessonProgress, LessonProgress.lesson_id == Lesson.id)
                     .where(LessonProgress.user_id == user_id, LessonProgress.status == "in_progress")
                     .order_by(LessonProgress.updated_at.desc()).limit(1)).first()
    if cur is None:
        done_ids = select(LessonProgress.lesson_id).where(LessonProgress.user_id == user_id,
                                                          LessonProgress.status == "completed")
        cur = db.execute(select(Lesson.slug, Lesson.title, Course.slug).join(Course)
                         .where(Lesson.id.not_in(done_ids)).order_by(Course.position, Lesson.position).limit(1)).first()
    current_lesson = {"slug": cur[0], "title": cur[1], "course_slug": cur[2]} if cur else None

    # 30-day chart
    start = today - timedelta(days=29)
    local_day = func.date(func.timezone(get_settings().timezone, Submission.created_at))
    per_day = db.execute(select(local_day, func.count(), func.count().filter(Submission.is_correct))
                         .where(Submission.user_id == user_id, local_day >= start).group_by(local_day)).all()
    pd = {d: (n, c) for d, n, c in per_day}
    secs = {d: s for d, s in act}
    chart = []
    for i in range(30):
        d = start + timedelta(days=i)
        n, c = pd.get(d, (0, 0))
        chart.append({"date": d.isoformat(), "submissions": n, "correct": c, "minutes": round(secs.get(d, 0) / 60)})

    earned = db.execute(select(Achievement, UserAchievement.earned_at)
                        .outerjoin(UserAchievement, and_(UserAchievement.achievement_key == Achievement.key,
                                                         UserAchievement.user_id == user_id))
                        .order_by(Achievement.position)).all()
    achievements = [{"key": a.key, "title": a.title, "description": a.description, "icon": a.icon,
                     "earned_at": at.isoformat() if at else None} for a, at in earned]

    return {
        "lessons": {"completed": done_lessons, "total": total_lessons},
        "exercises": {"solved": solved, "total": total_ex},
        "projects": {"completed": projects_done, "total": len(pp),
                     "tasks_solved": sum(p["solved"] for p in pp.values()), "tasks_total": sum(p["total"] for p in pp.values())},
        "submissions": {"total": subs, "correct": correct, "accuracy": accuracy},
        "streak": streak,
        "learning_seconds": total_seconds,
        "level": level_for(user_points(db, user_id)),
        "courses": courses,
        "skills": skills,
        "recent_exercises": recent_ex,
        "current_lesson": current_lesson,
        "activity": chart,
        "achievements": achievements,
    }


def solved_exercise_ids(db: Session, user_id: int) -> set[int]:
    return set(db.scalars(select(Submission.exercise_id).distinct().where(Submission.user_id == user_id,
                                                                       Submission.is_correct)))


def attempted_exercise_ids(db: Session, user_id: int) -> set[int]:
    return set(db.scalars(select(Submission.exercise_id).distinct().where(Submission.user_id == user_id)))

