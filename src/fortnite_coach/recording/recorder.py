"""Start/stop an ffmpeg recording. Only ever started by an explicit user action.

Windows can cut off screen capture at any moment: Desktop Duplication reports
DXGI_ERROR_ACCESS_LOST when the display mode changes or a full-screen app takes over,
which is exactly what happens when Fortnite opens or gets focus. ffmpeg then exits.

So a recording is a series of PARTS: if ffmpeg exits while the user is still recording,
the part written so far is kept and capture restarts automatically. Nothing heavy happens
here; joining the parts is done later (recording/merge.py), after the game.
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from pathlib import Path

from fortnite_coach.recording.command import RecordingPlan
from fortnite_coach.video.ffmpeg_tools import NO_WINDOW

log = logging.getLogger(__name__)

MIN_PART_BYTES = 16 * 1024   # smaller files contain no usable video
FAST_FAIL_S = 3.0            # a part that dies this fast counts as a failed restart
MAX_FAST_FAILS = 8           # give up after this many fast failures in a row
MAX_BACKOFF_S = 3.0


class RecorderState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    STOPPING = "stopping"
    FAILED = "failed"


def default_output_dir() -> Path:
    return Path.home() / "Videos" / "Fortnite AI Coach"


def new_output_path(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"fortnite_{datetime.now():%Y-%m-%d_%H-%M-%S}.mp4"


PlanFactory = Callable[[int], RecordingPlan]


class Recorder:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.state = RecorderState.IDLE
        self.plan: RecordingPlan | None = None      # plan of the current part
        self.error: str = ""
        self.parts: list[Path] = []                 # valid parts of the current/last recording
        self.restarts = 0                           # automatic restarts in the current recording
        self._factory: PlanFactory | None = None
        self._proc: subprocess.Popen | None = None
        self._log = None
        self._started = 0.0
        self._part_started = 0.0
        self._part_index = 0
        self._fast_fails = 0
        self._restart_at: float | None = None

    @property
    def is_recording(self) -> bool:
        return self.state is RecorderState.RECORDING

    @property
    def elapsed_s(self) -> float:
        return time.monotonic() - self._started if self.is_recording else 0.0

    # ------------------------------------------------------------------ control
    def start(self, plan_or_factory: RecordingPlan | PlanFactory) -> None:
        if self.is_recording:
            return  # idempotent: a second hotkey press does nothing
        if isinstance(plan_or_factory, RecordingPlan):
            fixed = plan_or_factory
            self._factory = lambda _i: fixed
        else:
            self._factory = plan_or_factory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.error, self.parts, self.restarts = "", [], 0
        self._part_index, self._fast_fails, self._restart_at = 0, 0, None
        self._started = time.monotonic()
        self.state = RecorderState.RECORDING
        self._start_part(first=True)

    def _start_part(self, first: bool = False) -> None:
        self._part_index += 1
        self.plan = self._factory(self._part_index)
        self._log = open(self.log_dir / "recorder.log", "w" if first else "a", encoding="utf-8")
        if not first:
            self._log.write(f"\n--- capture restarted automatically (part {self._part_index}) ---\n")
            self._log.flush()
        self._proc = subprocess.Popen(
            self.plan.args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self._log,
            creationflags=NO_WINDOW,
        )
        self._part_started = time.monotonic()

    def poll(self) -> RecorderState:
        """Called by a UI timer. Detects ffmpeg exiting on its own and resumes capture."""
        if not self.is_recording:
            return self.state
        now = time.monotonic()
        if self._proc is None:  # waiting to restart after a failure
            if self._restart_at is not None and now >= self._restart_at:
                self._restart_at = None
                self.restarts += 1
                self._start_part()
            return self.state
        if self._proc.poll() is None:
            return self.state
        code = self._proc.returncode
        lived = now - self._part_started
        self._close_part()
        tail = self._read_log_tail()
        log.warning("Capture part %d ended by itself after %.1fs (exit %s): %s",
                    self._part_index, lived, code, tail[-300:])
        self._fast_fails = self._fast_fails + 1 if lived < FAST_FAIL_S else 0
        if self._fast_fails >= MAX_FAST_FAILS:
            self.state = RecorderState.FAILED
            self.error = tail
            return self.state
        self._restart_at = now + min(MAX_BACKOFF_S, 0.5 * self._fast_fails)
        return self.state

    def stop(self, timeout: float = 15) -> list[Path]:
        """Finish the current part cleanly ('q') and return every valid part, in order."""
        if not self.is_recording:
            return []
        self.state = RecorderState.STOPPING
        self._restart_at = None
        if self._proc is not None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.write(b"q")
                    self._proc.stdin.flush()
                    self._proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass
            try:
                self._proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait()
            self._close_part()
        self.state = RecorderState.IDLE
        return list(self.parts)

    # ------------------------------------------------------------------ helpers
    def _close_part(self) -> None:
        if self._log:
            self._log.close()
            self._log = None
        self._proc = None
        out = self.plan.output if self.plan else None
        if out and out.is_file():
            if out.stat().st_size >= MIN_PART_BYTES:
                if out not in self.parts:
                    self.parts.append(out)
            else:
                out.unlink(missing_ok=True)  # an empty/unplayable stub is not a recording

    def _read_log_tail(self) -> str:
        try:
            return (self.log_dir / "recorder.log").read_text(encoding="utf-8", errors="replace")[-600:].strip()
        except OSError:
            return ""
