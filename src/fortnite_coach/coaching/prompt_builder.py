"""Build the coach prompt from the taxonomy and knowledge base (no hard-coded advice)."""

from __future__ import annotations

from fortnite_coach.coaching import taxonomy
from fortnite_coach.core.game_modes import GameMode
from fortnite_coach.core.skills import Skill


# What a strong coach pays most attention to in each mode (season-independent).
MODE_HINTS = {
    GameMode.CREATIVE_FREE_BUILD: "Free build practice: judge mechanics only (building sequences, cranking 90s, edits, build-edit "
                                  "combos, waterfalls, piece swaps, consistency). There is no opponent, so do not judge fights or game sense.",
    GameMode.REALISTIC_1V1: "Realistic 1v1: protection before shooting, piece control, retakes, edit timing, pre-firing, weapon swaps, "
                            "and when to reset or disengage.",
    GameMode.BOX_FIGHTS: "Box fights: piece control (take and lock walls, cones, floors), phasing, trapping, "
                         "edit-and-shoot timing, pre-firing edits, shotgun-to-SMG swaps, right-hand peeks and resets.",
    GameMode.ZONE_WARS: "Zone wars: early rotations, storm decisions, positioning vs. other players, third parties, "
                        "and fights while moving.",
    GameMode.RANKED: "Ranked: fight selection, third-party awareness, rotations, resource management, endgame layers.",
    GameMode.BATTLE_ROYALE: "Battle Royale: fight selection, third parties, rotations, resources, and fight execution.",
    GameMode.OTHER: "Judge whatever is visible; say what could not be judged.",
}


def fmt_ts(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def system_instruction(mode: GameMode, focus: list[str], language: str, knowledge: list[tuple[str, str]],
                       season: list[tuple[str, str, str, str]] | None = None, player_notes: str = "") -> str:
    """season: [(title, content, as_of 'YYYY-MM-DD', source)] - only fresh, sourced facts."""
    lang = "Hebrew" if language == "he" else "English"
    focus_names = ", ".join(focus) or "all skills"
    lines = [
        "You are an elite competitive Fortnite coach (keyboard and mouse player) reviewing a recorded match.",
        f"Game mode: {mode.value}. Focus skills: {focus_names}.",
        "What matters most in this mode: " + MODE_HINTS.get(mode, MODE_HINTS[GameMode.OTHER]),
        *([f"The player says they struggle with (their own words): \"{player_notes.strip()[:600]}\". "
           "Pay special attention to these situations and say clearly whether the video confirms it."]
          if player_notes.strip() else []),
        "",
        "STRICT RULES:",
        "- Judge ONLY what is visible or audible in the video. Never invent events.",
        "- Every mistake and good play needs a concrete timestamp (absolute video time MM:SS) and visible evidence.",
        "- If something cannot be judged from the video, add it to not_determinable instead of guessing.",
        f"- Never infer: {', '.join(taxonomy.NOT_MEASURABLE_EN)}.",
        "- Give no generic advice like 'improve your building'. Say exactly what happened, what was better, why,",
        "  and one specific drill to practice the fix.",
        "- Report good plays honestly too (difficulty easy/medium/hard); do not inflate them.",
        "- Prefer the most specific code; use OTHER only when no code fits.",
        "- Be concrete about sides and pieces (left/right wall, cone, floor, ramp) when the video shows them.",
        "- A skill score (0-100) is allowed only when this segment shows enough evidence; otherwise null.",
        "- Weapon stats, items and season meta change: do not state them as current facts.",
        "- stats: COUNT only what you can see or hear in this segment. A shot = the player's firing animation,",
        "  muzzle flash or gunshot sound; a hit = a hit marker or damage number on an opponent; a headshot = a",
        "  hit whose damage number is yellow/gold (white = body). An edit attempt =",
        "  the edit grid/outline appears; completed = the piece actually opens/changes. Use null for any count",
        "  you cannot make reliably (e.g. frames too sparse). Never estimate a count you did not observe.",
        "- For every mistake, search_query is an ENGLISH phrase (4-9 words) the player would type on YouTube/TikTok",
        "  to find a tutorial for exactly that situation: name the mechanic and context (e.g. 'fortnite how to",
        "  pre fire after double edit box fight'), not a generic topic.",
        f"- Write every other free-text field in {lang}. Keep codes and skill names exactly as listed.",
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
    if season:
        lines += ["", "CURRENT SEASON NOTES (researched with sources; use only if clearly relevant to what you see):"]
        lines += [f"- {title}: {content} (as of {as_of}, source: {src})" for title, content, as_of, src in season]
    return "\n".join(lines)


def segment_prompt(start_s: float, end_s: float, index: int, total: int) -> str:
    return (f"Analyze ONLY this part of the video: {fmt_ts(start_s)} to {fmt_ts(end_s)} "
            f"(segment {index + 1} of {total}). Use absolute video timestamps. Return JSON matching the schema.")
