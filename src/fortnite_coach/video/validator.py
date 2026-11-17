from __future__ import annotations

from pathlib import Path

from fortnite_coach.core.errors import VideoError
from fortnite_coach.core.game_modes import SUPPORTED_VIDEO_EXTENSIONS


def validate_video_path(path: str | Path) -> Path:
    """Cheap checks before running ffprobe. Raises VideoError with an i18n key."""
    p = Path(path)
    if p.suffix.lower() == ".replay":
        raise VideoError("replay", i18n_key="video.err_replay")
    if p.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
        raise VideoError("unsupported", i18n_key="video.err_format")
    if not p.is_file():
        raise VideoError("missing", i18n_key="video.err_missing")
    if p.stat().st_size == 0:
        raise VideoError("empty", i18n_key="video.err_empty")
    return p
