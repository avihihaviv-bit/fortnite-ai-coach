"""Merge validated segment results into one report (pure functions, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass, field

from fortnite_coach.ai.gemini_response_parser import ParsedItem, ParsedSegment
from fortnite_coach.coaching.levels import xp_for_play


@dataclass
class SkillAggregate:
    skill: str
    score: float | None
    evidence_count: int
    confidence: float | None


@dataclass
class XpAward:
    item: ParsedItem
    amount: int


@dataclass
class AggregatedReport:
    summary: str
    mistakes: list[ParsedItem] = field(default_factory=list)
    good_plays: list[ParsedItem] = field(default_factory=list)
    skills: list[SkillAggregate] = field(default_factory=list)
    xp: list[XpAward] = field(default_factory=list)
    not_determinable: list[str] = field(default_factory=list)
    dropped: int = 0


def _dedupe(items: list[ParsedItem]) -> list[ParsedItem]:
    seen, out = set(), []
    for it in sorted(items, key=lambda x: x.start_s):
        key = (it.code, it.skill, int(it.start_s // 3))
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def aggregate(segments: list[ParsedSegment]) -> AggregatedReport:
    rep = AggregatedReport(summary="\n".join(s.summary for s in segments if s.summary))
    for s in segments:
        rep.mistakes += s.mistakes
        rep.good_plays += s.good_plays
        rep.not_determinable += [x for x in s.not_determinable if x not in rep.not_determinable]
        rep.dropped += s.dropped
    rep.mistakes = _dedupe(rep.mistakes)
    rep.good_plays = _dedupe(rep.good_plays)

    by_skill: dict[str, list] = {}
    for s in segments:
        for a in s.assessments:
            by_skill.setdefault(a.skill, []).append(a)
    for skill, items in by_skill.items():
        scored = [a for a in items if a.score is not None and a.evidence_count > 0]
        evidence = sum(a.evidence_count for a in scored)
        score = round(sum(a.score * a.evidence_count for a in scored) / evidence, 1) if evidence else None
        confs = [a.confidence for a in scored if a.confidence is not None]
        rep.skills.append(SkillAggregate(skill, score, evidence, round(sum(confs) / len(confs), 2) if confs else None))

    for g in rep.good_plays:
        amount = xp_for_play(g.difficulty, g.confidence, g.evidence)
        if amount > 0:
            rep.xp.append(XpAward(g, amount))
    return rep
