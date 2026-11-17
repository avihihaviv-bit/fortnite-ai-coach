"""Dashboard statistics computed ONLY from stored analysis results.

Rules (no invented numbers):
- A skill has a rating only if at least one stored score for it is non-null
  and backed by evidence_count > 0.
- Overall rating needs at least MIN_SKILLS_FOR_OVERALL rated skills.
- Strongest/weakest need at least two rated skills to be meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select

from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import Report, Session, SessionStatus, SkillScore

MIN_SKILLS_FOR_OVERALL = 3


@dataclass
class SkillStat:
    average: float
    samples: int  # number of reports with evidence for this skill


@dataclass
class DashboardStats:
    analyzed_sessions: int = 0
    skills: dict[str, SkillStat] = field(default_factory=dict)
    overall: float | None = None
    strongest: str | None = None
    weakest: str | None = None


def dashboard_stats(db: Database) -> DashboardStats:
    with db.session() as s:
        analyzed = s.scalar(
            select(func.count(Session.id)).join(Report).where(Session.status == SessionStatus.COMPLETED)
        ) or 0
        rows = s.execute(
            select(SkillScore.skill, func.avg(SkillScore.score), func.count(SkillScore.id))
            .where(SkillScore.score.is_not(None), SkillScore.evidence_count > 0)
            .group_by(SkillScore.skill)
        ).all()
    stats = DashboardStats(analyzed_sessions=analyzed)
    stats.skills = {skill: SkillStat(round(float(avg), 1), int(n)) for skill, avg, n in rows}
    if len(stats.skills) >= MIN_SKILLS_FOR_OVERALL:
        stats.overall = round(sum(v.average for v in stats.skills.values()) / len(stats.skills), 1)
    if len(stats.skills) >= 2:
        ordered = sorted(stats.skills.items(), key=lambda kv: kv[1].average)
        stats.weakest, stats.strongest = ordered[0][0], ordered[-1][0]
    return stats
