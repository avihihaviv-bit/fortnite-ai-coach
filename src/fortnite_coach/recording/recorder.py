"""Start/stop an ffmpeg recording process. Only ever started by an explicit user action."""

from __future__ import annotations

import subprocess
import time
from datetime import datetime
from enum import Enum
from pathlib import Path

from fortnite_coach.recording.command import RecordingPlan
from fortnite_coach.video.ffmpeg_tools import NO_WINDOW


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


class Recorder:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.state = RecorderState.IDLE
        self.plan: RecordingPlan | None = None
        self.error: str = ""
        self._proc: subprocess.Popen | None = None
        self._log = None
        self._started = 0.0

    @property
    def is_recording(self) -> bool:
        return self.state is RecorderState.RECORDING

    @property
    def elapsed_s(self) -> float:
        return time.monotonic() - self._started if self.is_recording else 0.0

    def start(self, plan: RecordingPlan) -> None:
        if self.is_recording:
            return  # idempotent: a second hotkey press does nothing
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._log = open(self.log_dir / "recorder.log", "w", encoding="utf-8")
        self.plan, self.error = plan, ""
        self._proc = subprocess.Popen(
            plan.args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self._log,
            creationflags=NO_WINDOW,
        )
        self._started = time.monotonic()
        self.state = RecorderState.RECORDING

    def poll(self) -> RecorderState:
        """Detect ffmpeg exiting on its own (crash, device lost, test duration ended)."""
        if self.is_recording and self._proc is not None and self._proc.poll() is not None:
            code = self._proc.returncode
            self._finish()
            if code == 0:
                self.state = RecorderState.IDLE
            else:
                self.state = RecorderState.FAILED
                self.error = self._read_log_tail()
        return self.state

    def stop(self, timeout: float = 15) -> Path | None:
        """Ask ffmpeg to finish cleanly ('q'), so the file is finalized. Returns the output path."""
        if not self.is_recording or self._proc is None:
            return None
        self.state = RecorderState.STOPPING
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
        self._finish()
        self.state = RecorderState.IDLE
        out = self.plan.output if self.plan else None
        return out if out and out.is_file() and out.stat().st_size > 0 else None

    def _finish(self) -> None:
        if self._log:
            self._log.close()
            self._log = None
        self._proc = None

    def _read_log_tail(self) -> str:
        try:
            return (self.log_dir / "recorder.log").read_text(encoding="utf-8", errors="replace")[-600:].strip()
        except OSError:
            return ""
