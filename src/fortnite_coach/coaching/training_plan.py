"""Personal training plan, built ONLY from the player's analyzed sessions (no generic plan).

Priority order:
1. Mistakes repeated across sessions (strongest evidence of a habit).
2. Mistakes from the latest session, high severity first.
3. Lowest evidence-backed skill scores.
Every plan starts with a warm-up. Difficulty follows the skill score (lower score -> easier drill).
Each exercise stores WHY it was chosen, with the session count / timestamp / the coach's note.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select, update

from fortnite_coach.coaching.exercises_catalog import BY_ID, CATALOG, WARMUP_ID, ExerciseTemplate, templates_for_mistake, templates_for_skill
from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import Exercise, Mistake, Report, TrainingPlan
from fortnite_coach.db.repositories import report_repo, stats_repo

MAX_FOCUS = 3          # exercises besides the warm-up
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Issue:
    kind: str              # repeated | latest | weak_skill
    skill: str
    code: str | None = None
    sessions: int = 0
    score: float | None = None
    timestamp_s: float | None = None
    note: str = ""         # the coach's own drill suggestion from the video


def target_difficulty(score: float | None) -> str:
    if score is None or score < 50:
        return "easy"
    return "medium" if score < 75 else "hard"


_RANK = {"easy": 0, "medium": 1, "hard": 2}


def pick(templates: list[ExerciseTemplate], difficulty: str, used: set[str]) -> ExerciseTemplate | None:
    options = [t for t in templates if t.id not in used]
    if not options:
        return None
    return min(options, key=lambda t: abs(_RANK[t.difficulty] - _RANK[difficulty]))


def collect_issues(db: Database) -> list[Issue]:
    stats = stats_repo.dashboard_stats(db)
    scores = {k: v.average for k, v in stats.skills.items()}
    issues: list[Issue] = []
    seen_codes: set[str] = set()
    with db.session() as s:
        latest_id = s.scalar(select(Report.id).order_by(Report.created_at.desc(), Report.id.desc()).limit(1))
        latest = list(s.scalars(select(Mistake).where(Mistake.report_id == latest_id))) if latest_id else []
        notes = {}
        for m in s.scalars(select(Mistake).order_by(Mistake.id.desc())):
            notes.setdefault(m.code, (m.how_to_practice, m.timestamp_s))
    for r in report_repo.repeated_mistakes(db):
        note, ts = notes.get(r.code, ("", None))
        issues.append(Issue("repeated", r.skill, r.code, r.sessions, scores.get(r.skill), ts, note))
        seen_codes.add(r.code)
    for m in sorted(latest, key=lambda m: (SEVERITY_ORDER.get(m.severity, 1), m.timestamp_s or 0)):
        if m.code in seen_codes or m.code == "OTHER":
            continue
        seen_codes.add(m.code)
        issues.append(Issue("latest", m.skill, m.code, 1, scores.get(m.skill), m.timestamp_s, m.how_to_practice))
    for skill, score in sorted(scores.items(), key=lambda kv: kv[1]):
        issues.append(Issue("weak_skill", skill, score=score))
    return issues


def generate_plan(db: Database) -> int | None:
    """Create a new active plan (old plans are kept as history). Returns plan id, or None without data."""
    if report_repo.latest_report_id(db) is None:
        return None
    issues = collect_issues(db)
    chosen: list[tuple[ExerciseTemplate, Issue | None]] = [(BY_ID[WARMUP_ID], None)]
    used = {WARMUP_ID}
    for issue in issues:
        if len(chosen) > MAX_FOCUS:
            break
        pool = templates_for_mistake(issue.code) if issue.code else templates_for_skill(issue.skill)
        t = pick(pool, target_difficulty(issue.score), used)
        if t:
            chosen.append((t, issue))
            used.add(t.id)
    with db.session() as s:
        s.execute(update(TrainingPlan).values(is_active=False))
        report_ids = [r for (r,) in s.execute(select(Report.id).order_by(Report.id.desc()).limit(10))]
        plan = TrainingPlan(is_active=True, based_on_report_ids=report_ids)
        for order, (t, issue) in enumerate(chosen):
            reason = {"kind": "warmup"} if issue is None else {
                "kind": issue.kind, "skill": issue.skill, "code": issue.code, "sessions": issue.sessions,
                "score": issue.score, "t": issue.timestamp_s, "note": issue.note}
            plan.exercises.append(Exercise(
                template_id=t.id, name=t.name.en, category=t.category, skill=t.skill.value, goal=t.goal.en,
                instructions=t.instructions.en, duration_min=t.duration_min, difficulty=t.difficulty,
                success_criteria=t.success.en, level_up_when=t.level_up.en, map_type=t.map_type.en,
                reason=json.dumps(reason, ensure_ascii=False),
                source_mistake_codes=[issue.code] if issue and issue.code else [], order=order))
        s.add(plan)
        s.flush()
        return plan.id
