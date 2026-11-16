"""Visual theme: color tokens + Qt stylesheet."""

from __future__ import annotations

from fortnite_coach.config.paths import resource_path


class Colors:
    BG = "#121317"          # graphite window background
    PANEL = "#1A1C22"       # cards
    PANEL_DARK = "#0E0F12"  # sidebar
    PANEL_HOVER = "#22252D"
    BORDER = "#2A2D36"
    TEXT = "#E8EAF0"
    TEXT_MUTED = "#8B90A0"
    TEXT_FAINT = "#5C6170"
    BLUE = "#3B82F6"
    PURPLE = "#8B5CF6"
    GREEN = "#22C55E"
    AMBER = "#F59E0B"
    RED = "#EF4444"


def stylesheet() -> str:
    qss = resource_path("ui/theme.qss").read_text(encoding="utf-8")
    # Longest names first so @PANEL does not clobber @PANEL_DARK.
    for name in sorted((n for n in dir(Colors) if n.isupper()), key=len, reverse=True):
        qss = qss.replace(f"@{name}", getattr(Colors, name))
    return qss
