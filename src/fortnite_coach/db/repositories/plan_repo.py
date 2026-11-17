"""Training plan access, completion tracking and 'which training works'."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import Exercise, ExerciseCompletion, Mistake, Report, TrainingPlan


def active_plan(db: Database) -> TrainingPlan | None:
    with db.session() as s:
        return s.scalars(select(TrainingPlan).where(TrainingPlan.is_active.is_(True))
                         .options(selectinload(TrainingPlan.exercises).selectinload(Exercise.completions))
                         .order_by(TrainingPlan.id.desc())).first()


def complete_exercise(db: Database, exercise_id: int, minutes: int | None, rating: int | None, notes: str = "") -> None:
    if rating is not None and not 1 <= rating <= 5:
        raise ValueError("rating must be 1-5")
    with db.session() as s:
        if s.get(Exercise, exercise_id) is None:
            raise ValueError("unknown exercise")
        s.add(ExerciseCompletion(exercise_id=exercise_id, minutes=minutes, self_rating=rating, notes=notes))


def undo_last_completion(db: Database, exercise_id: int) -> None:
    with db.session() as s:
        c = s.scalars(select(ExerciseCompletion).where(ExerciseCompletion.exercise_id == exercise_id)
                      .order_by(ExerciseCompletion.id.desc())).first()
        if c:
            s.delete(c)


@dataclass
class TrainingTotals:
    completions: int
    minutes: int
    this_week: int


def totals(db: Database, since: datetime | None = None) -> TrainingTotals:
    with db.session() as s:
        n = s.scalar(select(func.count(ExerciseCompletion.id))) or 0
        mins = s.scalar(select(func.coalesce(func.sum(ExerciseCompletion.minutes), 0))) or 0
        week = s.scalar(select(func.count(ExerciseCompletion.id)).where(ExerciseCompletion.completed_at >= since)) \
            if since else 0
    return TrainingTotals(int(n), int(mins), int(week or 0))


@dataclass
class TrainingEffect:
    template_id: str
    completions: int
    before_per_session: float  # target mistakes per analyzed session before the first completion
    after_per_session: float   # ... and after it
    sessions_after: int


def training_effects(db: Database) -> list[TrainingEffect]:
    """Measured, not guessed: needs analyzed sessions both before AND after the training started."""
    out: list[TrainingEffect] = []
    with db.session() as s:
        rows = s.execute(select(Exercise.template_id, Exercise.source_mistake_codes,
                                func.min(ExerciseCompletion.completed_at), func.count(ExerciseCompletion.id))
                         .join(ExerciseCompletion, ExerciseCompletion.exercise_id == Exercise.id)
                         .group_by(Exercise.id)).all()
        reports = list(s.execute(select(Report.id, Report.created_at)).all())
        for template_id, codes, first, n in rows:
            if not codes or not template_id:
                continue
            before = [r for r, at in reports if at < first]
            after = [r for r, at in reports if at >= first]
            if not before or not after:
                continue

            def rate(ids):
                cnt = s.scalar(select(func.count(Mistake.id)).where(Mistake.report_id.in_(ids), Mistake.code.in_(codes)))
                return round((cnt or 0) / len(ids), 2)

            out.append(TrainingEffect(template_id, int(n), rate(before), rate(after), len(after)))
    return out
