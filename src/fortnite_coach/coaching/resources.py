"""Learning resources from the internet, matched to the player's own mistakes.

The links are search links (YouTube / Google) built from a curated query per mistake,
so they always show current tutorials and never point at a made-up video.
Queries are in English: most competitive Fortnite coaching content is in English.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from fortnite_coach.coaching import taxonomy

QUERIES: dict[str, str] = {
    # building
    "BUILD_UNPROTECTED_SIDE": "fortnite protect yourself while building tutorial",
    "BUILD_LATE_PROTECTION": "fortnite how to protect instantly when shot tutorial",
    "BUILD_LOST_HIGH_GROUND": "fortnite high ground retake tutorial",
    "BUILD_FAILED_RETAKE": "fortnite best high ground retakes guide",
    "BUILD_TUNNEL_GAP": "fortnite how to tunnel properly tutorial",
    "BUILD_OVERBUILD": "fortnite stop overbuilding material management",
    "BUILD_PANIC_SPAM": "fortnite how to build under pressure calmly",
    "BUILD_LOW_GROUND_EXPOSED": "fortnite low ground survival before retake",
    "BUILD_SLOW_HEIGHT": "fortnite how to do fast 90s tutorial",
    # editing
    "EDIT_FAILED": "fortnite edit accuracy drill tutorial",
    "EDIT_SLOW": "fortnite how to edit faster tutorial",
    "EDIT_EXPOSED_AFTER": "fortnite edit reset tutorial",
    "EDIT_REPEATED": "fortnite unpredictable edits box fight",
    "EDIT_WRONG_TIMING": "fortnite when to edit in fights timing",
    "EDIT_CROSSHAIR_OFF": "fortnite crosshair placement while editing",
    "EDIT_NO_PRE_EDIT": "fortnite pre edit tutorial",
    # piece control
    "PC_LOST_WALL": "fortnite piece control take walls tutorial",
    "PC_ATTACK_WITHOUT_PROTECTION": "fortnite protect before taking wall piece control",
    "PC_OPPONENT_ESCAPED": "fortnite trap opponent box fight piece control",
    "PC_UNSAFE_PEEK": "fortnite right hand peek explained",
    "PC_NO_FOLLOW_UP": "fortnite piece control convert into damage",
    "PC_NO_LOCK_AFTER_TAKE": "fortnite take wall then cone piece control",
    # aim
    "AIM_CROSSHAIR_LOW": "fortnite crosshair placement tutorial",
    "AIM_MISSED_OPEN_SHOT": "fortnite shotgun aim tips",
    "AIM_EARLY_SHOT": "fortnite stop panic shooting aim tips",
    "AIM_LOST_TRACKING": "fortnite tracking aim training",
    "AIM_WRONG_WEAPON_RANGE": "fortnite which weapon at what range guide",
    # movement
    "MOVE_STATIC_IN_FIGHT": "fortnite movement in fights strafing tips",
    "MOVE_PREDICTABLE_STRAFE": "fortnite unpredictable movement tips",
    "MOVE_BAD_JUMP": "fortnite when not to jump in fights",
    "MOVE_INEFFICIENT_PATH": "fortnite efficient movement rotation tips",
    # mechanics
    "MECH_NO_PRE_FIRE": "fortnite how to pre fire tutorial",
    "MECH_SLOW_SWAP": "fortnite fast weapon swap shotgun smg tutorial",
    "MECH_BROKEN_SEQUENCE": "fortnite build edit combos practice routine",
    "MECH_UNSAFE_WATERFALL": "fortnite how to waterfall safely tutorial",
    "MECH_RAMP_RUSH_NO_COVER": "fortnite ramp rush with protection tutorial",
    "MECH_MISSED_JUMP_SHOT": "fortnite jump shot timing tips",
    "MECH_SLOW_PIECE_SWAP": "fortnite wall replace piece swap tutorial",
    # game sense
    "GS_LATE_ROTATION": "fortnite how to rotate early guide",
    "GS_BAD_FIGHT_SELECTION": "fortnite when to take fights game sense",
    "GS_THIRD_PARTIED": "fortnite avoid getting third partied",
    "GS_OVERPUSH": "fortnite when to push and when to back off",
    "GS_NO_DISENGAGE": "fortnite how to disengage from fights",
    "GS_LOW_RESOURCES": "fortnite resource management mats heals",
    "GS_ENDGAME_POSITION": "fortnite endgame positioning guide",
    # fight execution
    "FIGHT_NO_OPENING_PROTECTION": "fortnite how to start a fight safely",
    "FIGHT_NO_FOLLOW_UP": "fortnite follow up after damage push",
    "FIGHT_NO_RESET": "fortnite reset and heal in box fights",
}

SKILL_QUERIES: dict[str, str] = {
    "building": "fortnite building tutorial for competitive",
    "editing": "fortnite editing tutorial for competitive",
    "piece_control": "fortnite piece control guide",
    "aim": "fortnite aim training routine",
    "movement": "fortnite movement tips competitive",
    "game_sense": "fortnite game sense guide competitive",
    "fight_execution": "fortnite box fighting guide",
    "positioning": "fortnite positioning guide",
    "decision_making": "fortnite decision making fights",
    "mechanics": "fortnite mechanics practice routine",
}


def query_for(code: str | None, skill: str | None = None) -> str:
    if code and code in QUERIES:
        return QUERIES[code]
    if code and code in taxonomy.MISTAKES_BY_CODE:
        return "fortnite " + taxonomy.MISTAKES_BY_CODE[code].en.split("(")[0].strip().lower()
    return SKILL_QUERIES.get(skill or "", "fortnite competitive tips")


def youtube_url(query: str) -> str:
    return "https://www.youtube.com/results?search_query=" + quote_plus(query)


def google_url(query: str) -> str:
    return "https://www.google.com/search?q=" + quote_plus(query)


def tiktok_url(query: str) -> str:
    return "https://www.tiktok.com/search?q=" + quote_plus(query)


def best_query(code: str | None, skill: str | None, ai_query: str | None = None) -> str:
    """The AI's phrase for this exact situation when it gave one, else the curated phrase for the mistake."""
    return (ai_query or "").strip() or query_for(code, skill)


def links_html(code: str | None, skill: str | None, label_search: str, ai_query: str | None = None) -> str:
    """'Search: «phrase»' + YouTube · TikTok · Google links for the same phrase."""
    from html import escape

    q = best_query(code, skill, ai_query)
    style = "color:#A78BFA"
    # \u2066...\u2069 isolates the English phrase so it reads correctly inside Hebrew (RTL) text
    return (f"{label_search} <b>\u2066\"{escape(q)}\"\u2069</b><br>"
            f"<a href='{youtube_url(q)}' style='{style}'>YouTube</a> &nbsp;·&nbsp; "
            f"<a href='{tiktok_url(q)}' style='{style}'>TikTok</a> &nbsp;·&nbsp; "
            f"<a href='{google_url(q)}' style='{style}'>Google</a>")
