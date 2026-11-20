"""App-wide recording controller: buttons, hotkeys and the sidebar indicator all use it."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from fortnite_coach.config.settings import RecordingSettings
from fortnite_coach.core.errors import CoachError
from fortnite_coach.recording import capabilities
from fortnite_coach.recording.capabilities import Capabilities
from fortnite_coach.recording.command import build_command
from fortnite_coach.recording.recorder import Recorder, RecorderState, default_output_dir, new_output_path
from fortnite_coach.video.ffmpeg_tools import find_ffmpeg
from fortnite_coach.workers.task import run_task


class RecordingController(QObject):
    state_changed = Signal(str)          # RecorderState value
    tick = Signal(float)                 # elapsed seconds while recording
    finished = Signal(object)            # list[str]: parts of the finished recording (joined later)
    interrupted = Signal(int)            # capture was cut off and resumed automatically (restart count)
    failed = Signal(str)                 # i18n key or error text
    capabilities_ready = Signal(object)  # Capabilities | None

    def __init__(self, log_dir: Path, settings_provider, *, source_override: str | None = None):
        super().__init__()
        self.recorder = Recorder(log_dir)
        self._settings = settings_provider  # callable -> AppSettings
        self.caps: Capabilities | None = None
        self.caps_error: str | None = None
        self.detecting = False
        self.hotkey_errors: list[str] = []  # combinations Windows refused (used by another program)
        self._source_override = source_override  # "test" in automated tests only
        self.test_part_seconds: float | None = None  # tests only: make each synthetic part end by itself
        self._seen_restarts = 0
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._on_tick)

    # ---- capability detection (user-triggered, runs a few short ffmpeg checks) ----
    def detect(self) -> None:
        if self.detecting:
            return
        self.detecting = True
        app_settings = self._settings()

        def work():
            return capabilities.detect(find_ffmpeg(app_settings.ffmpeg_path))

        run_task(work, self._caps_done, self._caps_failed)

    def _caps_done(self, caps: Capabilities) -> None:
        self.detecting, self.caps, self.caps_error = False, caps, None
        self.capabilities_ready.emit(caps)

    def _caps_failed(self, err: Exception) -> None:
        self.detecting, self.caps = False, None
        self.caps_error = getattr(err, "i18n_key", "error.generic")
        self.capabilities_ready.emit(None)

    # ---- recording ----
    @property
    def is_recording(self) -> bool:
        return self.recorder.is_recording

    def chosen_encoder(self, rec: RecordingSettings) -> str | None:
        if self.caps is None:
            return None
        if rec.encoder != "auto" and rec.encoder in self.caps.working_encoders:
            return rec.encoder
        return self.caps.best_encoder

    def start(self) -> bool:
        if self.is_recording:
            return True
        app_settings = self._settings()
        rec = app_settings.recording
        source = self._source_override or (self.caps.capture_backend if self.caps else None)
        encoder = "libx264" if self._source_override == "test" else self.chosen_encoder(rec)
        if source is None or encoder is None:
            self.failed.emit("rec.err_unavailable")
            return False
        try:
            ffmpeg = find_ffmpeg(app_settings.ffmpeg_path)
            folder = Path(rec.output_dir) if rec.output_dir else default_output_dir()
            base = new_output_path(folder)

            def plan_for(part: int):  # each automatic restart writes the next part
                return build_command(ffmpeg, source, encoder, rec, base.with_name(f"{base.stem}_part{part}.mp4"),
                                     test_duration_s=self.test_part_seconds)

            self.recorder.start(plan_for)
            self._seen_restarts = 0
        except (CoachError, OSError, ValueError) as e:
            self.failed.emit(getattr(e, "i18n_key", "rec.err_start"))
            return False
        self._timer.start()
        self.state_changed.emit(RecorderState.RECORDING.value)
        return True

    def stop(self) -> None:
        if not self.is_recording:
            return
        self._timer.stop()
        parts = self.recorder.stop()
        self.state_changed.emit(RecorderState.IDLE.value)
        if parts:
            self.finished.emit([str(p) for p in parts])
        else:
            self.failed.emit("rec.err_empty")

    def toggle(self) -> None:
        self.stop() if self.is_recording else self.start()

    def _on_tick(self) -> None:
        state = self.recorder.poll()
        if self.recorder.restarts != self._seen_restarts:
            self._seen_restarts = self.recorder.restarts
            self.interrupted.emit(self._seen_restarts)
        if state is RecorderState.RECORDING:
            self.tick.emit(self.recorder.elapsed_s)
            return
        self._timer.stop()
        self.state_changed.emit(state.value)
        parts = list(self.recorder.parts)
        if parts:  # keep whatever was captured, even if capture finally gave up
            self.finished.emit([str(p) for p in parts])
        if state is RecorderState.FAILED:
            self.failed.emit(self.recorder.error or "rec.err_start")
