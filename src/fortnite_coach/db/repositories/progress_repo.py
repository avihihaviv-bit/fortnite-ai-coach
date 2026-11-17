"""Progress over time, computed only from stored analysis results and training logs.

Labels the UI must keep:
- skill scores, overall rating          -> AI estimate
- counts (sessions, mistakes, XP, minutes, completions) -> measured from your data
No percentages of improvement are produced: only the raw before/after values.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import ExerciseCompletion, Mistake, Report, Session, SkillScore, XpEvent

RESOLVED_AFTER = 3          # a mistake is "resolved" after this many later comparable sessions without it
MIN_SKILLS_FOR_OVERALL = 3


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _analyzed_minutes(coverage: list | None) -> float:
    return sum(c["end_s"] - c["start_s"] for c in (coverage or []) if c.get("analyzed")) / 60.0


@dataclass
class SessionPoint:
    report_id: int
    at: datetime
    game_mode: str
    analyzed_min: float
    scores: dict[str, float]          # AI estimate, only evidence-backed
    overall: float | None             # AI estimate, needs >= 3 scored skills
    mistakes: int
    xp: int

    @property
    def mistakes_per_min(self) -> float | None:
        return round(self.mistakes / self.analyzed_min, 2) if self.analyzed_min >= 0.5 else None


def timeline(db: Database) -> list[SessionPoint]:
    with db.session() as s:
        reps = list(s.scalars(select(Report).options(selectinload(Report.session), selectinload(Report.skill_scores),
                                                     selectinload(Report.mistakes))
                              .order_by(Report.created_at, Report.id)))
        xp = dict(s.execute(select(XpEvent.report_id, func.sum(XpEvent.amount)).group_by(XpEvent.report_id)).all())
    out = []
    for r in reps:
        scores = {sc.skill: sc.score for sc in r.skill_scores if sc.score is not None and sc.evidence_count > 0}
        overall = round(sum(scores.values()) / len(scores), 1) if len(scores) >= MIN_SKILLS_FOR_OVERALL else None
        out.append(SessionPoint(r.id, _aware(r.created_at), r.session.game_mode, round(_analyzed_minutes(r.coverage), 2),
                                scores, overall, len(r.mistakes), int(xp.get(r.id, 0))))
    return out


@dataclass
class PeriodStats:
    key: str            # "2026-W47" or "2026-11"
    sessions: int = 0
    analyzed_min: float = 0.0
    mistakes: int = 0
    xp: int = 0
    completions: int = 0
    training_min: int = 0

    @property
    def mistakes_per_min(self) -> float | None:
        return round(self.mistakes / self.analyzed_min, 2) if self.analyzed_min >= 0.5 else None


def _week_key(dt: datetime) -> str:
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def _month_key(dt: datetime) -> str:
    return f"{dt.year}-{dt.month:02d}"


def periods(db: Database, monthly: bool = False) -> list[PeriodStats]:
    key = _month_key if monthly else _week_key
    buckets: dict[str, PeriodStats] = {}
    for p in timeline(db):
        b = buckets.setdefault(key(p.at), PeriodStats(key(p.at)))
        b.sessions += 1
        b.analyzed_min += p.analyzed_min
        b.mistakes += p.mistakes
        b.xp += p.xp
    with db.session() as s:
        for at, minutes in s.execute(select(ExerciseCompletion.completed_at, ExerciseCompletion.minutes)):
            k = key(_aware(at))
            b = buckets.setdefault(k, PeriodStats(k))
            b.completions += 1
            b.training_min += minutes or 0
    return [buckets[k] for k in sorted(buckets)]


@dataclass
class MistakeStatus:
    code: str
    skill: str
    status: str               # repeated | active | resolved
    sessions: int
    total: int
    first_seen: datetime
    last_seen: datetime
    clean_after: int          # later comparable sessions without it


def mistake_statuses(db: Database) -> list[MistakeStatus]:
    """Resolved = seen before, then absent in RESOLVED_AFTER later sessions of the SAME game mode."""
    points = timeline(db)
    order = {p.report_id: i for i, p in enumerate(points)}
    mode_of = {p.report_id: p.game_mode for p in points}
    with db.session() as s:
        rows = s.execute(select(Mistake.code, Mistake.skill, Mistake.report_id).where(Mistake.code != "OTHER")).all()
    by_code: dict[tuple[str, str], list[int]] = defaultdict(list)
    for code, skill, rid in rows:
        by_code[(code, skill)].append(rid)
    out = []
    for (code, skill), rids in by_code.items():
        reports = sorted(set(rids), key=lambda r: order[r])
        last = reports[-1]
        later_same_mode = [p for p in points[order[last] + 1:] if p.game_mode == mode_of[last]]
        if len(later_same_mode) >= RESOLVED_AFTER:
            status = "resolved"
        elif len(reports) >= 2:
            status = "repeated"
        else:
            status = "active"
        out.append(MistakeStatus(code, skill, status, len(reports), len(rids), points[order[reports[0]]].at,
                                 points[order[last]].at, len(later_same_mode)))
    rank = {"repeated": 0, "active": 1, "resolved": 2}
    return sorted(out, key=lambda m: (rank[m.status], -m.sessions, -m.total))


@dataclass
class Record:
    key: str                  # i18n key suffix
    value: str
    at: datetime | None
    detail: str = ""


def personal_records(db: Database) -> list[Record]:
    pts = timeline(db)
    recs: list[Record] = []
    if not pts:
        return recs
    best: dict[str, tuple[float, datetime]] = {}
    for p in pts:
        for skill, sc in p.scores.items():
            if skill not in best or sc > best[skill][0]:
                best[skill] = (sc, p.at)
    for skill, (sc, at) in sorted(best.items()):
        recs.append(Record("best_score", f"{sc:.0f}", at, skill))
    top_xp = max(pts, key=lambda p: p.xp)
    if top_xp.xp:
        recs.append(Record("most_xp", str(top_xp.xp), top_xp.at))
    rated = [p for p in pts if p.mistakes_per_min is not None]
    if rated:
        clean = min(rated, key=lambda p: p.mistakes_per_min)
        recs.append(Record("fewest_mistakes", f"{clean.mistakes_per_min:g}", clean.at))
    with db.session() as s:
        hard = s.scalar(select(func.count(XpEvent.id)).where(XpEvent.difficulty == "hard")) or 0
        days = sorted({_aware(d).date() for (d,) in s.execute(select(ExerciseCompletion.completed_at))})
    if hard:
        recs.append(Record("hard_plays", str(hard), None))
    if days:
        streak = best_streak = 1
        for a, b in zip(days, days[1:]):
            streak = streak + 1 if (b - a).days == 1 else 1
            best_streak = max(best_streak, streak)
        recs.append(Record("training_streak", str(best_streak), None))
    return recs


@dataclass
class Comparison:
    older: SessionPoint
    newer: SessionPoint
    score_changes: list[tuple[str, float, float]] = field(default_factory=list)   # skill, before, after (both exist)
    gone: list[str] = field(default_factory=list)       # mistake codes in older but not newer
    new: list[str] = field(default_factory=list)
    still: list[str] = field(default_factory=list)


def compare(db: Database, older_id: int, newer_id: int) -> Comparison | None:
    pts = {p.report_id: p for p in timeline(db)}
    if older_id not in pts or newer_id not in pts:
        return None
    a, b = pts[older_id], pts[newer_id]
    if a.at > b.at:
        a, b = b, a
    with db.session() as s:
        codes_a = {c for (c,) in s.execute(select(Mistake.code).where(Mistake.report_id == a.report_id, Mistake.code != "OTHER"))}
        codes_b = {c for (c,) in s.execute(select(Mistake.code).where(Mistake.report_id == b.report_id, Mistake.code != "OTHER"))}
    cmp = Comparison(a, b)
    cmp.score_changes = [(k, a.scores[k], b.scores[k]) for k in sorted(a.scores) if k in b.scores]
    cmp.gone, cmp.new, cmp.still = sorted(codes_a - codes_b), sorted(codes_b - codes_a), sorted(codes_a & codes_b)
    return cmp


def default_pair(db: Database) -> tuple[int, int] | None:
    """Latest session vs the previous session of the same game mode (comparable sessions)."""
    pts = timeline(db)
    if len(pts) < 2:
        return None
    latest = pts[-1]
    prev = [p for p in pts[:-1] if p.game_mode == latest.game_mode]
    return ((prev[-1] if prev else pts[-2]).report_id, latest.report_id)
