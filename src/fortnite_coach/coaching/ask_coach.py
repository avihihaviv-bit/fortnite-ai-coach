"""Ask the coach: the player writes what they struggle with; Gemini answers with their own data as context.

One text request per question (no video). Counted in the daily request limit. The answer is structured
(explanation, drills, search phrases) so the app can show drills and YouTube / TikTok / Google links.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from fortnite_coach.ai import usage_tracker
from fortnite_coach.ai.gemini_response_parser import clean_query
from fortnite_coach.coaching.stats_view import score10
from fortnite_coach.core.errors import GeminiError
from fortnite_coach.db.repositories import report_repo, stats_repo

MAX_QUESTION = 800


class DrillOut(BaseModel):
    name: str
    how: str = Field(description="Exact steps: map type, what to do, reps or minutes, what counts as success")
    minutes: int = Field(description="Minutes, 5-30")


class CoachAnswerOut(BaseModel):
    answer: str = Field(description="Direct, concrete coaching answer to the player's question")
    key_points: list[str] = Field(default_factory=list, description="2-5 short things to remember in-game")
    drills: list[DrillOut] = Field(default_factory=list, description="1-3 drills that fix exactly this")
    search_queries: list[str] = Field(default_factory=list, description=(
        "1-3 ENGLISH YouTube/TikTok search phrases (4-9 words) for tutorials on exactly this problem"))


@dataclass
class CoachAnswer:
    question: str
    answer: str
    key_points: list[str] = field(default_factory=list)
    drills: list[dict] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)


def player_context(db, notes: str = "") -> str:
    """What the app knows from the player's analyzed videos (facts only; nothing invented)."""
    lines = []
    st = stats_repo.dashboard_stats(db)
    if st.skills:
        lines.append("Skill scores 1-10 (AI estimates from their videos): " + ", ".join(
            f"{k} {score10(v.average)}" for k, v in sorted(st.skills.items(), key=lambda kv: kv[1].average)))
    for g in report_repo.struggles(db, 5):
        lines.append(f"Seen mistake: {g.code} ({g.skill}), in {g.sessions} session(s); example: {g.example[:140]}")
    reports = report_repo.list_reports(db, 1)
    if reports:
        d = report_repo.report_detail(db, reports[0].report_id)
        s = getattr(d.report, "stats", None) or {} if d else {}
        if s.get("shots_fired"):
            lines.append(f"Last session counted: shots {s.get('shots_fired')}, hits {s.get('shots_hit', '?')}, "
                         f"headshots {s.get('headshots', '?')}, edits {s.get('edits_attempted', '?')} "
                         f"(worked {s.get('edits_completed', '?')})")
    if notes.strip():
        lines.append(f"The player wrote about their struggles: {notes.strip()[:600]}")
    return "\n".join(lines) or "No analyzed videos yet: answer from general competitive knowledge and say so."


def system_instruction(language: str) -> str:
    lang = "Hebrew" if language == "he" else "English"
    return "\n".join([
        "You are an elite, friendly competitive Fortnite coach (keyboard and mouse). The player asks you about",
        "something they struggle with. Use their data below when it is relevant, and say when you are going",
        "beyond it. Be concrete: name the exact mechanic, keybind habit, build sequence, timing or decision,",
        "what to do instead, and why. No generic advice. Weapon stats and season meta change: do not state",
        "them as current facts. Never invent numbers about the player that are not in their data.",
        f"Write answer, key_points and drills in {lang}. search_queries are always in English.",
    ])


def ask(db, settings, service, question: str) -> CoachAnswer:
    q = (question or "").strip()[:MAX_QUESTION]
    if not q:
        raise GeminiError("empty question", i18n_key="coach.err_empty")
    usage_tracker.check_budget(db, settings.limits, 1)
    from fortnite_coach.i18n.translator import get_translator

    lang = get_translator().language
    prompt = f"PLAYER DATA:\n{player_context(db, settings.player_struggles)}\n\nQUESTION:\n{q}"
    try:
        res = service.ask_json(system_instruction(lang), prompt, CoachAnswerOut)
    except GeminiError as e:
        usage_tracker.record(db, model=service.model, kind="coach", success=False, error_code=e.i18n_key)
        raise
    usage_tracker.record(db, model=service.model, kind="coach", success=True, prompt_tokens=res.prompt_tokens,
                         output_tokens=res.output_tokens)
    try:
        out = CoachAnswerOut.model_validate(json.loads(res.text))
    except Exception as e:
        raise GeminiError("invalid answer", i18n_key="gemini.err_invalid_response") from e
    drills = [{"name": d.name.strip(), "how": d.how.strip(), "minutes": max(1, min(60, int(d.minutes or 10)))}
              for d in out.drills if d.name.strip()][:3]
    queries = [q2 for q2 in (clean_query(x) for x in out.search_queries) if q2][:3]
    return CoachAnswer(q, out.answer.strip(), [k.strip() for k in out.key_points if k.strip()][:5], drills, queries)


# ---- history (local only) ------------------------------------------------------------------------
HISTORY_KEY = "coach_chat"
HISTORY_MAX = 20


def load_history(db) -> list[CoachAnswer]:
    from fortnite_coach.db.models import Setting

    with db.session() as s:
        row = s.get(Setting, HISTORY_KEY)
        items = (row.value or []) if row else []
    out = []
    for it in items:
        try:
            out.append(CoachAnswer(**it))
        except TypeError:
            continue
    return out


def save_to_history(db, ans: CoachAnswer) -> None:
    from dataclasses import asdict

    from fortnite_coach.db.models import Setting

    items = [asdict(a) for a in [ans, *load_history(db)]][:HISTORY_MAX]
    with db.session() as s:
        row = s.get(Setting, HISTORY_KEY)
        if row is None:
            s.add(Setting(key=HISTORY_KEY, value=items))
        else:
            row.value = items
