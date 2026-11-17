"""User data deletion."""

from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy import delete

from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import (
    ApiUsage,
    Exercise,
    ExerciseCompletion,
    Mistake,
    Report,
    Session,
    SkillScore,
    TrainingPlan,
    Video,
)


def delete_all_analysis_data(db: Database) -> None:
    """Remove sessions, reports, scores, mistakes, plans and usage history.
    Keeps settings, the player profile and the knowledge base. Never touches the
    user's video files (only their database references)."""
    with db.session() as s:
        for model in (ExerciseCompletion, Exercise, TrainingPlan, Mistake, SkillScore, Report, Session, Video, ApiUsage):
            s.execute(delete(model))


def clear_cache(cache_dir: Path) -> int:
    """Delete derived frames/clips. Returns bytes freed."""
    freed = 0
    if not cache_dir.exists():
        return 0
    for p in cache_dir.rglob("*"):
        if p.is_file():
            freed += p.stat().st_size
    for child in cache_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
    return freed
