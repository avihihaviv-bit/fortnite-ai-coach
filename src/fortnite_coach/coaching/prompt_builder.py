"""Build the coach prompt from the taxonomy and knowledge base (no hard-coded advice)."""

from __future__ import annotations

from fortnite_coach.coaching import taxonomy
from fortnite_coach.core.game_modes import GameMode
from fortnite_coach.core.skills import Skill


def fmt_ts(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def system_instruction(mode: GameMode, focus: list[str], language: str, knowledge: list[tuple[str, str]]) -> str:
    lang = "Hebrew" if language == "he" else "English"
    focus_names = ", ".join(focus) or "all skills"
    lines = [
        "You are an elite competitive Fortnite coach (keyboard and mouse player) reviewing a recorded match.",
        f"Game mode: {mode.value}. Focus skills: {focus_names}.",
        "",
        "STRICT RULES:",
        "- Judge ONLY what is visible or audible in the video. Never invent events.",
        "- Every mistake and good play needs a concrete timestamp (absolute video time MM:SS) and visible evidence.",
        "- If something cannot be judged from the video, add it to not_determinable instead of guessing.",
        f"- Never infer: {', '.join(taxonomy.NOT_MEASURABLE_EN)}.",
        "- Give no generic advice like 'improve your building'. Say exactly what happened, what was better, why,",
        "  and one specific drill to practice the fix.",
        "- Report good plays honestly too (difficulty easy/medium/hard); do not inflate them.",
        "- A skill score (0-100) is allowed only when this segment shows enough evidence; otherwise null.",
        "- Weapon stats, items and season meta change: do not state them as current facts.",
        f"- Write every free-text field in {lang}. Keep codes and skill names exactly as listed.",
        "",
        "SKILLS (use these exact values): " + ", ".join(s.value for s in Skill),
        "",
        "EVALUATION CRITERIA:",
    ]
    for skill, crits in taxonomy.CRITERIA.items():
        lines.append(f"- {skill.value}: " + "; ".join(c.en for c in crits))
    lines += ["", "MISTAKE CODES (or OTHER):"]
    lines += [f"- {m.code} [{m.skill.value}]: {m.en}" for m in taxonomy.MISTAKES]
    lines += ["", "GOOD PLAY CODES (or OTHER):"]
    lines += [f"- {g.code} [{g.skill.value}]: {g.en}" for g in taxonomy.GOOD_PLAYS]
    if knowledge:
        lines += ["", "COACHING FUNDAMENTALS (season-independent):"]
        lines += [f"- {title}: {content}" for title, content in knowledge]
    return "\n".join(lines)


def segment_prompt(start_s: float, end_s: float, index: int, total: int) -> str:
    return (f"Analyze ONLY this part of the video: {fmt_ts(start_s)} to {fmt_ts(end_s)} "
            f"(segment {index + 1} of {total}). Use absolute video timestamps. Return JSON matching the schema.")
