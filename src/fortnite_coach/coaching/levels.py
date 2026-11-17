"""Levels & XP, earned only from good plays the coach actually saw in a video.

Rules (kept simple and transparent so the player can trust the number):
- XP per good play = difficulty base (easy 10, medium 25, hard 50) x confidence, rounded.
- A play counts only with confidence >= MIN_CONFIDENCE, non-empty evidence, and a
  timestamp inside the analyzed part of the video.
- Mistakes never remove XP: the level shows progress. The separate skill score
  ("current form", AI estimate) reflects mistakes.
- Level curve: XP needed to go from level L to L+1 = 100 + 50*(L-1).
"""

from __future__ import annotations

from dataclasses import dataclass

DIFFICULTY_XP = {"easy": 10, "medium": 25, "hard": 50}
MIN_CONFIDENCE = 0.6
TIERS = ("bronze", "silver", "gold", "platinum", "diamond", "master", "legend")
LEVELS_PER_TIER = 5


def xp_for_play(difficulty: str, confidence: float | None, evidence: str) -> int:
    if difficulty not in DIFFICULTY_XP or confidence is None or confidence < MIN_CONFIDENCE:
        return 0
    if not (evidence or "").strip():
        return 0
    return int(round(DIFFICULTY_XP[difficulty] * min(confidence, 1.0)))


def xp_to_next(level: int) -> int:
    return 100 + 50 * (level - 1)


@dataclass(frozen=True)
class LevelInfo:
    level: int
    total_xp: int
    xp_into_level: int
    xp_for_next: int

    @property
    def progress(self) -> float:
        return self.xp_into_level / self.xp_for_next if self.xp_for_next else 0.0

    @property
    def tier(self) -> str:
        return TIERS[min((self.level - 1) // LEVELS_PER_TIER, len(TIERS) - 1)]


def level_from_xp(total_xp: int) -> LevelInfo:
    total = max(0, int(total_xp))
    level, remaining = 1, total
    while remaining >= xp_to_next(level):
        remaining -= xp_to_next(level)
        level += 1
    return LevelInfo(level=level, total_xp=total, xp_into_level=remaining, xp_for_next=xp_to_next(level))


def level_ups(before_xp: int, after_xp: int) -> int:
    """How many levels were gained between two XP totals."""
    return level_from_xp(after_xp).level - level_from_xp(before_xp).level
