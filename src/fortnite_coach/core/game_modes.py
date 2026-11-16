"""Game modes and analysis depth options."""

from __future__ import annotations

from enum import Enum


class GameMode(str, Enum):
    CREATIVE_FREE_BUILD = "creative_free_build"
    REALISTIC_1V1 = "realistic_1v1"
    BOX_FIGHTS = "box_fights"
    ZONE_WARS = "zone_wars"
    RANKED = "ranked"
    BATTLE_ROYALE = "battle_royale"
    OTHER = "other"

    @property
    def i18n_key(self) -> str:
        return f"mode.{self.value}"

    @property
    def is_training(self) -> bool:
        """Creative-style modes count as training sessions."""
        return self in TRAINING_MODES


TRAINING_MODES = frozenset(
    {GameMode.CREATIVE_FREE_BUILD, GameMode.REALISTIC_1V1, GameMode.BOX_FIGHTS, GameMode.ZONE_WARS}
)


class AnalysisDepth(str, Enum):
    QUICK = "quick"        # sampled frames only, single small request
    STANDARD = "standard"  # compressed low-fps clip
    DETAILED = "detailed"  # longer / higher-quality clip

    @property
    def i18n_key(self) -> str:
        return f"depth.{self.value}"


SUPPORTED_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".webm"})
