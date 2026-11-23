"""Reports, mistakes, good plays (XP) and the queries the UI needs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from fortnite_coach.coaching.aggregate import AggregatedReport
from fortnite_coach.coaching.levels import LevelInfo, level_from_xp
from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import Mistake, Report, Session, SessionStatus, SkillScore, Video, XpEvent


def xp_already_awarded(db: Database, fingerprint: str) -> bool:
    """The same video never gives XP twice (re-analysis cannot farm levels)."""
    with db.session() as s:
        n = s.scalar(select(func.count(XpEvent.id)).join(Report, XpEvent.report_id == Report.id)
                     .join(Session, Report.session_id == Session.id).join(Video, Session.video_id == Video.id)
                     .where(Video.fingerprint == fingerprint))
        return bool(n)


def save_report(db: Database, session_id: int, *, model: str, prompt_version: str, agg: AggregatedReport,
                coverage: list[dict], raw: list[dict], award_xp: bool) -> int:
    with db.session() as s:
        rep = Report(session_id=session_id, model=model, prompt_version=prompt_version, summary=agg.summary,
                     raw_json=json.dumps({"segments": raw, "not_determinable": agg.not_determinable,
                                          "dropped_items": agg.dropped}, ensure_ascii=False),
                     coverage=coverage, stats=agg.stats or {})
        rep.skill_scores = [SkillScore(skill=k.skill, score=k.score, confidence=k.confidence,
                                       evidence_count=k.evidence_count) for k in agg.skills]
        rep.mistakes = [Mistake(skill=m.skill, code=m.code, severity=m.severity, timestamp_s=m.start_s,
                                timestamp_end_s=m.end_s, what_happened=m.what_happened, better_option=m.better_option,
                                why=m.why, how_to_practice=m.how_to_practice, evidence=m.evidence,
                                confidence=m.confidence, search_query=m.search_query or "")
                        for m in agg.mistakes]
        s.add(rep)
        s.flush()
        if award_xp:
            for x in agg.xp:
                g = x.item
                s.add(XpEvent(report_id=rep.id, skill=g.skill, code=g.code, difficulty=g.difficulty, amount=x.amount,
                              timestamp_s=g.start_s, timestamp_end_s=g.end_s, description=g.what_happened,
                              evidence=g.evidence, confidence=g.confidence))
        sess = s.get(Session, session_id)
        sess.status = SessionStatus.COMPLETED
        sess.analyzed_at = datetime.now(timezone.utc)
        return rep.id


# ------------------------------------------------------------------ levels
def xp_totals(db: Database) -> dict[str, int]:
    with db.session() as s:
        return {k: int(v) for k, v in s.execute(select(XpEvent.skill, func.sum(XpEvent.amount)).group_by(XpEvent.skill))}


@dataclass
class Levels:
    overall: LevelInfo
    skills: dict[str, LevelInfo]


def levels(db: Database) -> Levels:
    totals = xp_totals(db)
    return Levels(overall=level_from_xp(sum(totals.values())),
                  skills={k: level_from_xp(v) for k, v in totals.items()})


# ------------------------------------------------------------------ history
@dataclass
class ReportRow:
    report_id: int
    session_id: int
    created_at: datetime
    video_path: str
    game_mode: str
    depth: str
    analyzed_s: float
    total_s: float
    mistakes: int
    xp: int


def list_reports(db: Database, limit: int = 50) -> list[ReportRow]:
    with db.session() as s:
        reps = list(s.scalars(select(Report).options(selectinload(Report.session).selectinload(Session.video),
                                                     selectinload(Report.mistakes))
                              .order_by(Report.created_at.desc(), Report.id.desc()).limit(limit)))
        xp = dict(s.execute(select(XpEvent.report_id, func.sum(XpEvent.amount)).group_by(XpEvent.report_id)).all())
    rows = []
    for r in reps:
        cov = r.coverage or []
        rows.append(ReportRow(r.id, r.session_id, r.created_at, r.session.video.path, r.session.game_mode,
                              r.session.depth, sum(c["end_s"] - c["start_s"] for c in cov if c.get("analyzed")),
                              sum(c["end_s"] - c["start_s"] for c in cov), len(r.mistakes), int(xp.get(r.id, 0))))
    return rows


@dataclass
class ReportDetail:
    report: Report
    video_path: str
    fingerprint: str
    game_mode: str
    mistakes: list[Mistake] = field(default_factory=list)
    good_plays: list[XpEvent] = field(default_factory=list)
    scores: list[SkillScore] = field(default_factory=list)
    not_determinable: list[str] = field(default_factory=list)
    dropped: int = 0


def report_detail(db: Database, report_id: int) -> ReportDetail | None:
    with db.session() as s:
        r = s.scalars(select(Report).where(Report.id == report_id).options(
            selectinload(Report.session).selectinload(Session.video), selectinload(Report.mistakes),
            selectinload(Report.skill_scores))).first()
        if r is None:
            return None
        plays = list(s.scalars(select(XpEvent).where(XpEvent.report_id == report_id).order_by(XpEvent.timestamp_s)))
    raw = json.loads(r.raw_json or "{}")
    return ReportDetail(r, r.session.video.path, r.session.video.fingerprint, r.session.game_mode,
                        sorted(r.mistakes, key=lambda m: m.timestamp_s or 0), plays, list(r.skill_scores),
                        raw.get("not_determinable", []), int(raw.get("dropped_items", 0)))


def latest_report_id(db: Database) -> int | None:
    with db.session() as s:
        return s.scalar(select(Report.id).order_by(Report.created_at.desc(), Report.id.desc()).limit(1))


# ------------------------------------------------------------------ skill pages / patterns
@dataclass
class Finding:
    kind: str  # "mistake" | "good"
    code: str
    skill: str
    timestamp_s: float | None
    text: str
    detail: str
    video_path: str
    report_id: int
    xp: int = 0


def findings_for_skill(db: Database, skill: str, limit: int = 12) -> list[Finding]:
    with db.session() as s:
        ms = s.execute(select(Mistake, Video.path, Report.id).join(Report, Mistake.report_id == Report.id)
                       .join(Session, Report.session_id == Session.id).join(Video, Session.video_id == Video.id)
                       .where(Mistake.skill == skill).order_by(Report.created_at.desc(), Mistake.timestamp_s)
                       .limit(limit)).all()
        gs = s.execute(select(XpEvent, Video.path, Report.id).join(Report, XpEvent.report_id == Report.id)
                       .join(Session, Report.session_id == Session.id).join(Video, Session.video_id == Video.id)
                       .where(XpEvent.skill == skill).order_by(XpEvent.amount.desc(), XpEvent.timestamp_s)
                       .limit(limit)).all()
    out = [Finding("good", g.code, g.skill, g.timestamp_s, g.description, g.evidence, p, rid, g.amount)
           for g, p, rid in gs]
    out += [Finding("mistake", m.code, m.skill, m.timestamp_s, m.what_happened,
                    m.better_option or m.how_to_practice, p, rid) for m, p, rid in ms]
    return out


@dataclass
class RepeatedMistake:
    code: str
    skill: str
    sessions: int
    total: int


@dataclass
class Struggle:
    code: str
    skill: str
    sessions: int        # analyzed sessions where it was seen
    total: int           # times seen
    query: str           # newest AI search phrase for it ("" -> curated phrase is used)
    example: str         # newest "what happened" text (the player's own moment)
    severity: str


_SEV = {"high": 3, "medium": 2, "low": 1}


def struggles(db: Database, limit: int = 5) -> list[Struggle]:
    """What the player struggles with most: repeated first, then severity, then recency. Evidence-based only."""
    with db.session() as s:
        rows = s.execute(select(Mistake.code, Mistake.skill, Mistake.report_id, Mistake.severity, Mistake.search_query,
                                Mistake.what_happened).order_by(Mistake.id.asc())).all()
    groups: dict[str, dict] = {}
    for code, skill, rid, sev, q, what in rows:
        key = code if code != "OTHER" else f"OTHER:{(q or what)[:40].lower()}"
        g = groups.setdefault(key, {"code": code, "skill": skill, "reports": set(), "total": 0, "query": "",
                                    "example": "", "sev": 0, "last": 0})
        g["reports"].add(rid)
        g["total"] += 1
        g["sev"] = max(g["sev"], _SEV.get(sev, 2))
        g["last"] = rid
        if q:
            g["query"] = q
        g["example"] = what
    ranked = sorted(groups.values(), key=lambda g: (-len(g["reports"]), -g["sev"], -g["total"], -g["last"]))
    inv = {v: k for k, v in _SEV.items()}
    return [Struggle(g["code"], g["skill"], len(g["reports"]), g["total"], g["query"], g["example"], inv[g["sev"]])
            for g in ranked[:limit]]


def latest_search_queries(db: Database) -> dict[str, str]:
    """The newest AI search phrase per mistake code (what to search for that exact problem)."""
    with db.session() as s:
        rows = s.execute(select(Mistake.code, Mistake.search_query).where(Mistake.search_query != "")
                         .order_by(Mistake.id.asc())).all()
    return {c: q for c, q in rows}


def repeated_mistakes(db: Database, min_sessions: int = 2) -> list[RepeatedMistake]:
    with db.session() as s:
        rows = s.execute(select(Mistake.code, Mistake.skill, func.count(func.distinct(Mistake.report_id)),
                                func.count(Mistake.id))
                         .where(Mistake.code != "OTHER").group_by(Mistake.code, Mistake.skill)).all()
    out = [RepeatedMistake(c, sk, int(n), int(t)) for c, sk, n, t in rows if n >= min_sessions]
    return sorted(out, key=lambda r: (-r.sessions, -r.total))


def find_report(db: Database, fingerprint: str, mode: str, depth: str, focus: list[str]) -> int | None:
    """An existing report for the same video and settings (re-running it would only duplicate history)."""
    with db.session() as s:
        rows = s.execute(select(Report.id, Session.focus_skills).join(Session, Report.session_id == Session.id)
                         .join(Video, Session.video_id == Video.id)
                         .where(Video.fingerprint == fingerprint, Session.game_mode == mode, Session.depth == depth)
                         .order_by(Report.id.desc())).all()
    for rid, f in rows:
        if sorted(f or []) == sorted(focus):
            return rid
    return None
