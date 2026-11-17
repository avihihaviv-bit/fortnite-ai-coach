"""Import a video: validate -> ffprobe metadata -> fingerprint -> thumbnails. Runs on a worker thread."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fortnite_coach.video.fingerprint import fingerprint
from fortnite_coach.video.frames import even_timestamps, extract_frames
from fortnite_coach.video.metadata import VideoMetadata, probe
from fortnite_coach.video.validator import validate_video_path

THUMB_COUNT = 4


@dataclass
class ImportedVideo:
    meta: VideoMetadata
    fingerprint: str
    thumbnails: list[Path] = field(default_factory=list)


def import_video(path: str | Path, frames_root: Path, ffprobe: str | None = None) -> ImportedVideo:
    p = validate_video_path(path)
    meta = probe(p, ffprobe)
    fp = fingerprint(p)
    thumb_dir = frames_root / fp[:16]
    existing = sorted(thumb_dir.glob("thumb_*.jpg")) if thumb_dir.exists() else []
    thumbs = existing or extract_frames(p, even_timestamps(meta.duration_s, THUMB_COUNT), thumb_dir, max_width=480, prefix="thumb")
    return ImportedVideo(meta=meta, fingerprint=fp, thumbnails=thumbs)
