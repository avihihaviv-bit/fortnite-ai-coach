"""Turn AI-counted stats and 0-100 skill scores into what the player reads (percentages, 1-10)."""

from __future__ import annotations

MIN_SHOTS = 5      # fewer shots: no shooting percentage (it would mean nothing)
MIN_HITS = 3       # fewer hits: no headshot percentage
MIN_EDITS = 3


def score10(score: float | None) -> str | None:
    """0-100 -> '1'..'10' with one decimal ('7.5'); None stays None (not enough evidence)."""
    if score is None:
        return None
    v = max(1.0, min(10.0, round(score / 10, 1)))
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _pct(part: int, whole: int) -> int:
    return round(100 * part / whole) if whole else 0


def stats_lines(stats: dict | None, tr) -> list[str]:
    """One line per stat. Shown only when there is enough to count; otherwise an honest 'not enough data'."""
    s = stats or {}
    lines = []
    nd = tr("common.not_enough_data")
    shots = s.get("shots_fired_for_shots_hit", s.get("shots_fired"))
    if "shots_hit" in s and shots and shots >= MIN_SHOTS:
        lines.append(tr("stats.accuracy", pct=_pct(s["shots_hit"], shots), hit=s["shots_hit"], shots=shots))
    else:
        lines.append(tr("stats.accuracy_none", nd=nd))
    hits = s.get("shots_hit_for_headshots")
    if "headshots" in s and hits and hits >= MIN_HITS:
        lines.append(tr("stats.headshots", pct=_pct(s["headshots"], hits), head=s["headshots"], hits=hits))
    else:
        lines.append(tr("stats.headshots_none", nd=nd))
    edits = s.get("edits_attempted_for_edits_completed", s.get("edits_attempted"))
    if "edits_completed" in s and edits and edits >= MIN_EDITS:
        lines.append(tr("stats.edits", pct=_pct(s["edits_completed"], edits), done=s["edits_completed"], tries=edits))
    else:
        lines.append(tr("stats.edits_none", nd=nd))
    fights = s.get("fights_for_fights_won", s.get("fights"))
    if fights:
        lines.append(tr("stats.fights", won=s.get("fights_won", "?"), fights=fights,
                        elims=s.get("eliminations", "?"), down=s.get("times_eliminated", "?")))
    total = s.get("_total")
    counted = max([v for k, v in s.items() if k.startswith("_") and k.endswith("_segments")] or [0])
    if total and counted and counted < total:
        lines.append(tr("stats.partial", n=counted, total=total))
    return lines
