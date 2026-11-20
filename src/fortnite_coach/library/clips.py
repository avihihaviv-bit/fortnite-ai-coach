"""Clip library: finds video files in folders the player chooses (Medal, NVIDIA, Xbox Game Bar, OBS...).

Only reads file names, sizes and dates; videos stay where they are and are never modified.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}
MAX_DEPTH = 4
MAX_FILES = 1000


@dataclass(frozen=True)
class Clip:
    path: str
    name: str
    size_bytes: int
    modified: datetime
    folder: str


def candidate_folders(home: Path | None = None, extra: list[Path] | None = None) -> list[tuple[str, Path]]:
    """(label key, folder) pairs where clipping tools save by default."""
    h = home or Path.home()
    videos = h / "Videos"
    out = [
        ("clips.src_medal", videos / "Medal"),
        ("clips.src_medal", h / "Medal"),
        ("clips.src_medal", Path("C:/Medal")),
        ("clips.src_app", videos / "Fortnite AI Coach"),
        ("clips.src_nvidia", videos / "Fortnite"),
        ("clips.src_nvidia", videos / "NVIDIA"),
        ("clips.src_xbox", videos / "Captures"),
        ("clips.src_videos", videos),
    ]
    for p in extra or []:
        out.append(("clips.src_custom", p))
    return out


def detected_folders(home: Path | None = None) -> list[tuple[str, Path]]:
    seen, out = set(), []
    for key, p in candidate_folders(home):
        try:
            if p.is_dir() and str(p).lower() not in seen:
                seen.add(str(p).lower())
                out.append((key, p))
        except OSError:
            continue
    return out


def scan(folders: list[Path], limit: int = MAX_FILES) -> list[Clip]:
    """Newest first. Skips our own cache/proxy files and folders we cannot read."""
    found: dict[str, Clip] = {}
    for root in folders:
        root = Path(root)
        if not root.is_dir():
            continue
        base_depth = len(root.parts)
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _e: None):
            depth = len(Path(dirpath).parts) - base_depth
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and depth < MAX_DEPTH]
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.suffix.lower() not in VIDEO_EXTS:
                    continue
                key = str(p.resolve()).lower()
                if key in found:
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                if st.st_size < 50_000:
                    continue
                found[key] = Clip(str(p), p.name, st.st_size, datetime.fromtimestamp(st.st_mtime), str(root))
            if len(found) >= limit * 2:
                break
    return sorted(found.values(), key=lambda c: c.modified, reverse=True)[:limit]
