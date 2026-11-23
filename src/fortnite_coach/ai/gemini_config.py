"""Central Gemini configuration. Free-Tier-first: only Flash-class models can be chosen."""

from __future__ import annotations

from dataclasses import dataclass

from fortnite_coach.core.game_modes import AnalysisDepth

# Known Flash models (used before the first connection test). Google retires models over time,
# so the connection test also discovers newer Flash models that the user's key can use.
# Only Flash-class models are ever offered: they have a Gemini API free tier. Pro models never are.
ALLOWED_MODELS: tuple[str, ...] = ("gemini-2.5-flash", "gemini-2.5-flash-lite")
DEFAULT_MODEL = ALLOWED_MODELS[0]

_EXCLUDE = ("tts", "image", "live", "audio", "embedding", "native", "thinking", "learnlm", "-exp", "computer")
PROMPT_VERSION = "4"


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


def is_flash_candidate(name: str) -> bool:
    n = name.lower()
    return n.startswith("gemini-") and "flash" in n and "pro" not in n and not any(x in n for x in _EXCLUDE)


def _rank(name: str) -> tuple:
    import re

    m = re.match(r"gemini-(\d+(?:\.\d+)?)", name)
    version = float(m.group(1)) if m else 0.0
    stable = "preview" not in name
    full = "lite" not in name
    return (stable, version, full, -len(name))


def usable_models(names) -> list[str]:
    """Flash models available for this key, best first: stable > preview, newer > older, full > lite."""
    return sorted({n for n in names if is_flash_candidate(n)}, key=_rank, reverse=True)


def live_model(available, main: str, chosen: str = "") -> str:
    """Model for Live Coach tips. Auto = the best "flash-lite" model the key can use: Google counts the free quota
    per model, so Live then does not eat the quota of the main analysis model (and lite answers faster)."""
    if chosen:
        return chosen
    lites = [n for n in usable_models(available or []) if "lite" in n.lower()]
    return lites[0] if lites else main


def is_allowed(model: str) -> bool:
    return model in ALLOWED_MODELS or is_flash_candidate(model)
