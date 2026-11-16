"""Filesystem locations used by the app.

Everything lives under a single per-user data directory:
- Windows: %APPDATA%\\FortniteAICoach
- other OS (development/tests): ~/.local/share/FortniteAICoach
The env var FORTNITE_COACH_HOME overrides it (used by tests).

Videos are NEVER copied here - only small derived files (frames, compressed
clips) live in the cache directory, and they can be deleted at any time.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from fortnite_coach import APP_ID

ENV_HOME = "FORTNITE_COACH_HOME"


def default_data_dir() -> Path:
    override = os.environ.get(ENV_HOME)
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_ID
    xdg = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(xdg) / APP_ID


@dataclass(frozen=True)
class AppPaths:
    root: Path

    @property
    def database(self) -> Path:
        return self.root / "coach.db"

    @property
    def cache_dir(self) -> Path:
        return self.root / "cache"

    @property
    def frames_dir(self) -> Path:
        return self.cache_dir / "frames"

    @property
    def clips_dir(self) -> Path:
        return self.cache_dir / "clips"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    def ensure(self) -> "AppPaths":
        for p in (self.root, self.cache_dir, self.frames_dir, self.clips_dir, self.logs_dir):
            p.mkdir(parents=True, exist_ok=True)
        return self

    @classmethod
    def default(cls) -> "AppPaths":
        return cls(default_data_dir())


def resource_path(relative: str) -> Path:
    """Path to a bundled resource, works both from source and in a PyInstaller EXE."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "fortnite_coach" / relative
    return Path(__file__).resolve().parent.parent / relative
