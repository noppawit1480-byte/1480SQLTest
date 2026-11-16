"""Content-as-code helpers. Lessons/exercises are reviewed in Git and seeded into the main DB.

Example results are NOT written by hand — the seeder executes every example on the sandbox and
stores the real output, so documentation can never drift from what PostgreSQL actually returns.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Example:
    title: str
    sql: str
    explain: list[str]                  # step-by-step explanation, one item per clause/line
    db: str | None = None               # defaults to the lesson's db
    writable: bool = False              # DDL/DML examples run on a throwaway copy at seed time


@dataclass
class Mistake:
    title: str
    wrong: str
    right: str
    why: str


@dataclass
class LessonDef:
    slug: str
    title: str
    summary: str
    objectives: list[str]
    content: str                        # markdown, Thai explanation of the concept
    examples: list[Example]
    mistakes: list[Mistake]
    related: list[str] = field(default_factory=list)
    db: str = "ecommerce"


@dataclass
class ExerciseDef:
    code: str
    title: str
    description: str                    # markdown
    difficulty: str                     # easy | medium | hard | expert
    category: str
    db: str
    solution: str
    hints: list[str]                    # exactly 3: idea → approach → keywords
    explanation: str
    lesson: str | None = None           # slug of the lesson this exercise closes
    order_matters: bool = False
    check_type: str = "select"          # select | dml
    check_sql: str | None = None        # dml only: query whose result is compared after running the answer
    check_column_names: bool = True


POINTS = {"easy": 10, "medium": 20, "hard": 30, "expert": 50}


@dataclass
class CourseDef:
    slug: str
    title: str
    level: str
    description: str
    lessons: list[LessonDef]
