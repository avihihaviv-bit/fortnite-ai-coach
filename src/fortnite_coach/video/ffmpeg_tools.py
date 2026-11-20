"""Locate ffmpeg / ffprobe and run them without opening console windows."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from fortnite_coach.core.errors import FFmpegNotFoundError

ENV_FFMPEG = "FORTNITE_COACH_FFMPEG"
ENV_FFPROBE = "FORTNITE_COACH_FFPROBE"

# On Windows, prevent a console window from flashing for every ffmpeg call.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# Background video work runs below normal priority so a running game keeps the CPU first.
LOW_PRIORITY = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)


def _bundled_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "ffmpeg"
    return Path(__file__).resolve().parents[3] / "vendor" / "ffmpeg"


def _find(name: str, configured: str | None, env_var: str) -> str:
    candidates: list[str | None] = [configured, os.environ.get(env_var)]
    exe = f"{name}.exe" if sys.platform == "win32" else name
    candidates.append(str(_bundled_dir() / exe))
    for c in candidates:
        if c and Path(c).is_file():
            return c
    found = shutil.which(name)
    if found:
        return found
    raise FFmpegNotFoundError(f"{name} not found")


def find_ffmpeg(configured: str | None = None) -> str:
    return _find("ffmpeg", configured, ENV_FFMPEG)


def find_ffprobe(configured: str | None = None) -> str:
    return _find("ffprobe", configured, ENV_FFPROBE)


def run(args: list[str], timeout: float = 60, low_priority: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, timeout=timeout,
        creationflags=NO_WINDOW | (LOW_PRIORITY if low_priority else 0),
        encoding="utf-8", errors="replace",
    )
