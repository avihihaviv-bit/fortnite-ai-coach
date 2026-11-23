"""Validate a Gemini segment response. Nothing is invented: invalid items are dropped and counted."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from fortnite_coach.ai.schemas import SegmentResult
from fortnite_coach.coaching.taxonomy import GOOD_PLAYS_BY_CODE, MISTAKES_BY_CODE
from fortnite_coach.core.errors import GeminiError
from fortnite_coach.core.skills import Skill

TOLERANCE_S = 2.0
_SKILLS = {s.value for s in Skill}
_SEVERITIES = {"low", "medium", "high"}
_DIFFICULTIES = {"easy", "medium", "hard"}


def parse_timestamp(text: str) -> float | None:
    """'02:14' / '1:02:14' / '134' / '134.5s' / '01:05-01:07' (first time) -> seconds."""
    t = (text or "").strip().lower()
    m = re.search(r"(?:(\d+):)?(\d{1,2}):(\d{2}(?:\.\d+)?)", t)
    if m:
        h, mi, se = m.groups()
        return int(h or 0) * 3600 + int(mi) * 60 + float(se)
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*s?", t)
    return float(m.group(1)) if m else None


def _norm(value: str) -> str:
    """'Piece Control' / 'piece-control' -> 'piece_control' (the model sometimes varies the spelling)."""
    return re.sub(r"[\s\-]+", "_", (value or "").strip().lower())


def _clamp01(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if 1.0 < f <= 100.0:  # given as a percentage (80 -> 0.8)
        f /= 100.0
    return max(0.0, min(1.0, f))


@dataclass
class ParsedItem:
    code: str
    skill: str
    start_s: float
    end_s: float
    what_happened: str
    evidence: str
    confidence: float | None
    severity: str = ""
    difficulty: str = ""
    better_option: str = ""
    why: str = ""
    how_to_practice: str = ""
    search_query: str = ""


def clean_query(q: str | None) -> str:
    """Keep the AI's search phrase short and plain (it goes into a URL)."""
    import re

    q = re.sub(r"[^\w\s'+-]", " ", (q or ""), flags=re.UNICODE)
    q = " ".join(q.split())[:90].strip()
    if len(q.split()) < 2:
        return ""
    return q if q.lower().startswith("fortnite") else f"fortnite {q}"


@dataclass
class ParsedAssessment:
    skill: str
    score: float | None
    evidence_count: int
    confidence: float | None
    rationale: str


@dataclass
class ParsedSegment:
    segment_index: int
    start_s: float
    end_s: float
    summary: str
    mistakes: list[ParsedItem] = field(default_factory=list)
    good_plays: list[ParsedItem] = field(default_factory=list)
    assessments: list[ParsedAssessment] = field(default_factory=list)
    not_determinable: list[str] = field(default_factory=list)
    dropped: int = 0  # items rejected by validation (shown to the user)
    stats: dict = field(default_factory=dict)  # validated counts (only keys the model could count)


STAT_KEYS = ("shots_fired", "shots_hit", "headshots", "edits_attempted", "edits_completed", "fights", "fights_won",
             "eliminations", "times_eliminated")
_PAIRS = (("shots_hit", "shots_fired"), ("headshots", "shots_hit"), ("edits_completed", "edits_attempted"), ("fights_won", "fights"))


def clean_stats(raw) -> dict:
    """Keep plausible non-negative counts; a part can never exceed its whole (e.g. hits <= shots)."""
    out = {}
    for k in STAT_KEYS:
        v = getattr(raw, k, None) if raw is not None and not isinstance(raw, dict) else (raw or {}).get(k)
        try:
            v = int(v) if v is not None else None
        except (TypeError, ValueError):
            v = None
        if v is not None and 0 <= v <= 5000:
            out[k] = v
    for part, whole in _PAIRS:
        if part in out and whole in out and out[part] > out[whole]:
            out.pop(part)  # contradictory: drop the part rather than invent a number
        elif part in out and whole not in out:
            out.pop(part)  # a percentage needs both
    return out


def load_segment_result(text: str) -> SegmentResult:
    try:
        return SegmentResult.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        raise GeminiError(str(e)[:300], i18n_key="gemini.err_invalid_response") from e


def _times(start: str, end: str, seg_start: float, seg_end: float) -> tuple[float, float] | None:
    s, e = parse_timestamp(start), parse_timestamp(end)
    if s is None:
        return None
    e = s if e is None or e < s else e
    if seg_start > TOLERANCE_S and s < seg_start - TOLERANCE_S and seg_start + s <= seg_end + TOLERANCE_S:
        # The model counted from the start of this segment instead of the start of the video
        # (relative and absolute ranges cannot overlap for segments after the first): convert.
        s, e = s + seg_start, e + seg_start
    if s < seg_start - TOLERANCE_S or s > seg_end + TOLERANCE_S:
        return None  # outside the analyzed part: cannot be trusted
    return max(s, seg_start), min(e, seg_end)


def validate_segment(result: SegmentResult, index: int, seg_start: float, seg_end: float) -> ParsedSegment:
    out = ParsedSegment(index, seg_start, seg_end, result.segment_summary.strip(),
                        not_determinable=[x for x in result.not_determinable if x.strip()])
    for m in result.mistakes:
        m.skill, m.severity, m.code = _norm(m.skill), _norm(m.severity), m.code.strip().upper()
        t = _times(m.start, m.end, seg_start, seg_end)
        if t is None or m.skill not in _SKILLS or not m.evidence.strip() or not m.what_happened.strip():
            out.dropped += 1
            continue
        code = m.code if m.code in MISTAKES_BY_CODE else "OTHER"
        out.mistakes.append(ParsedItem(
            code=code, skill=m.skill, start_s=t[0], end_s=t[1], what_happened=m.what_happened.strip(),
            evidence=m.evidence.strip(), confidence=_clamp01(m.confidence),
            severity=m.severity if m.severity in _SEVERITIES else "medium",
            better_option=m.better_option.strip(), why=m.why.strip(), how_to_practice=m.how_to_practice.strip(),
            search_query=clean_query(getattr(m, "search_query", ""))))
    for g in result.good_plays:
        g.skill, g.difficulty, g.code = _norm(g.skill), _norm(g.difficulty), g.code.strip().upper()
        t = _times(g.start, g.end, seg_start, seg_end)
        if t is None or g.skill not in _SKILLS or not g.evidence.strip() or g.difficulty not in _DIFFICULTIES:
            out.dropped += 1
            continue
        code = g.code if g.code in GOOD_PLAYS_BY_CODE else "OTHER"
        out.good_plays.append(ParsedItem(
            code=code, skill=g.skill, start_s=t[0], end_s=t[1], what_happened=g.what_happened.strip(),
            evidence=g.evidence.strip(), confidence=_clamp01(g.confidence), difficulty=g.difficulty))
    for a in result.skill_assessments:
        a.skill = _norm(a.skill)
        if a.skill not in _SKILLS:
            out.dropped += 1
            continue
        score = a.score if a.score is not None and 0 <= a.score <= 100 and a.evidence_count > 0 else None
        out.assessments.append(ParsedAssessment(a.skill, None if score is None else float(score),
                                                max(0, a.evidence_count) if score is not None else 0,
                                                _clamp01(a.confidence), a.rationale.strip()))
    out.stats = clean_stats(getattr(result, "stats", None))
    return out


def shift_segment(seg: ParsedSegment, offset: float) -> ParsedSegment:
    """Times from an analysis copy that starts at `offset` -> absolute times in the original video."""
    if not offset:
        return seg
    seg.start_s += offset
    seg.end_s += offset
    for item in (*seg.mistakes, *seg.good_plays):
        item.start_s += offset
        item.end_s += offset
    return seg
