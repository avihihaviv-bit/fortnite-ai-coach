"""Read video metadata with ffprobe (measured values, not estimates)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from fortnite_coach.core.errors import VideoError
from fortnite_coach.video.ffmpeg_tools import find_ffprobe, run


@dataclass(frozen=True)
class VideoMetadata:
    path: str
    size_bytes: int
    duration_s: float
    width: int
    height: int
    fps: float | None
    codec: str
    has_audio: bool
    container: str


def _fps(rate: str | None) -> float | None:
    try:
        f = Fraction(rate) if rate else None
    except (ValueError, ZeroDivisionError):
        return None
    return round(float(f), 2) if f else None


def probe(path: str | Path, ffprobe: str | None = None) -> VideoMetadata:
    exe = find_ffprobe(ffprobe)
    res = run([exe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)], timeout=60)
    if res.returncode != 0:
        raise VideoError(res.stderr.strip()[:300], i18n_key="video.err_unreadable")
    data = json.loads(res.stdout or "{}")
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise VideoError("no video stream", i18n_key="video.err_no_video")
    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or video.get("duration") or 0)
    if duration <= 0:
        raise VideoError("zero duration", i18n_key="video.err_unreadable")
    return VideoMetadata(
        path=str(path),
        size_bytes=int(fmt.get("size") or Path(path).stat().st_size),
        duration_s=round(duration, 3),
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        fps=_fps(video.get("avg_frame_rate")) or _fps(video.get("r_frame_rate")),
        codec=str(video.get("codec_name") or "unknown"),
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
        container=str(fmt.get("format_name") or ""),
    )
