"""Live Coach screenshots: ffmpeg grabs one small JPEG every 2 seconds into a temp folder.

Uses the same Desktop Duplication capture as recording (frames stay on the GPU until the
tiny downscale), so the cost is far below a recording. Like recording, Windows can cut the
capture off (e.g. a display-mode change); the controller simply restarts it.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from fortnite_coach.video.ffmpeg_tools import LOW_PRIORITY, NO_WINDOW

FRAME_EVERY_S = 2


class FrameCapture:
    def __init__(self, ffmpeg: str, folder: Path, *, source: str = "ddagrab", monitor_index: int = 0):
        self.ffmpeg, self.folder, self.source, self.monitor_index = ffmpeg, folder, source, monitor_index
        self._proc: subprocess.Popen | None = None
        self.restarts = 0

    def command(self) -> list[str]:
        pattern = str(self.folder / "frame_%06d.jpg")
        if self.source == "ddagrab":
            inp = ["-f", "lavfi", "-i", f"ddagrab=output_idx={self.monitor_index}:framerate=2:draw_mouse=0"]
            vf = f"hwdownload,format=bgra,fps=1/{FRAME_EVERY_S},scale=1280:-2"
        elif self.source == "gdigrab":
            inp = ["-f", "gdigrab", "-framerate", "2", "-draw_mouse", "0", "-i", "desktop"]
            vf = f"fps=1/{FRAME_EVERY_S},scale=1280:-2"
        elif self.source == "test":  # automated tests only
            inp = ["-re", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=2"]
            vf = f"fps=1/{FRAME_EVERY_S}"
        else:
            raise ValueError(source_error := f"unknown source {self.source}")  # noqa: F841
        return [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *inp, "-vf", vf, "-q:v", "5",
                "-f", "image2", "-start_number", str(self._next_number()), pattern]

    def _next_number(self) -> int:
        nums = [int(p.stem.split("_")[1]) for p in self.folder.glob("frame_*.jpg") if p.stem.split("_")[1].isdigit()]
        return (max(nums) + 1) if nums else 1

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        self._proc = subprocess.Popen(self.command(), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL, creationflags=NO_WINDOW | LOW_PRIORITY)

    def ensure_running(self) -> None:
        """Restart if Windows cut the capture off."""
        if self._proc is not None and self._proc.poll() is not None:
            self.restarts += 1
            self.start()

    def latest(self, n: int) -> list[Path]:
        frames = sorted(self.folder.glob("frame_*.jpg"))
        # the newest file may still be being written: skip it
        ready = frames[:-1] if len(frames) > 1 else []
        return ready[-n:]

    def prune(self, keep: int) -> None:
        frames = sorted(self.folder.glob("frame_*.jpg"))
        for p in frames[:-keep]:
            p.unlink(missing_ok=True)

    def stop(self) -> None:
        if self._proc is not None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.write(b"q")
                    self._proc.stdin.flush()
                    self._proc.stdin.close()
                self._proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                self._proc.kill()
            self._proc = None
        shutil.rmtree(self.folder, ignore_errors=True)
