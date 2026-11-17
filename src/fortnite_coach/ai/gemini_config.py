"""Central Gemini configuration. Free-Tier-first: only Flash-class models can be chosen."""

from __future__ import annotations

from dataclasses import dataclass

from fortnite_coach.core.game_modes import AnalysisDepth

# Models the user may select. All have a free tier on the Gemini API (availability per key
# is verified by the connection test; the app never switches to another model on its own).
ALLOWED_MODELS: tuple[str, ...] = ("gemini-2.5-flash", "gemini-2.5-flash-lite")
DEFAULT_MODEL = ALLOWED_MODELS[0]
PROMPT_VERSION = "1"


@dataclass(frozen=True)
class DepthProfile:
    proxy_height: int     # analysis copy resolution
    fps: float            # frames per second Gemini samples from the video
    low_resolution: bool  # MEDIA_RESOLUTION_LOW = fewer tokens per frame


DEPTH_PROFILES: dict[AnalysisDepth, DepthProfile] = {
    AnalysisDepth.QUICK: DepthProfile(proxy_height=720, fps=0.5, low_resolution=True),
    AnalysisDepth.STANDARD: DepthProfile(proxy_height=720, fps=1.0, low_resolution=True),
    AnalysisDepth.DETAILED: DepthProfile(proxy_height=1080, fps=2.0, low_resolution=False),
}


def is_allowed(model: str) -> bool:
    return model in ALLOWED_MODELS
