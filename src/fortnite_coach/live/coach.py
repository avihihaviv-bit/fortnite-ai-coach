"""Live Coach (experimental, opt-in): every N seconds, the last few screenshots go to Gemini
and one short tip comes back, shown in a small overlay in the top-left corner.

Honest limits: tips arrive ~5-20 s after the moment (capture + network + model), screenshots
are 1 every 2 s, so the coach sees situations and habits, not sub-second edits. It only looks
at the screen like a viewer would: no game memory, no input, no automation.
"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from fortnite_coach.ai import usage_tracker
from fortnite_coach.ai.gemini_service import classify
from fortnite_coach.live.capture import FRAME_EVERY_S, FrameCapture
from fortnite_coach.video.ffmpeg_tools import find_ffmpeg
from fortnite_coach.workers.task import run_task

log = logging.getLogger(__name__)

# errors after which more requests cannot succeed today / without user action
FATAL_KEYS = {"gemini.err_key", "gemini.err_no_free_quota", "gemini.err_quota_daily", "gemini.err_region",
              "gemini.err_model", "gemini.err_permission", "gemini.err_no_key"}

SYSTEM = {
    "en": ("You are a live Fortnite coach looking over the player's shoulder. You get the last few screenshots "
           "(oldest first, 2 seconds apart). Give ONE short, concrete, actionable tip about what you can actually "
           "see right now: protection while building, high ground, health/shield and heals, materials, zone/storm "
           "position, weapon choice for the range, crosshair placement and pre-firing, exposed sides. Max 12 words, imperative, "
           "no greeting, no emojis. If the screenshots are not live gameplay (menus, lobby, loading, spectating, "
           "another app) or nothing useful is visible, answer exactly NONE. Never guess what you cannot see."),
    "he": ("אתה מאמן פורטנייט חי שמסתכל מעבר לכתף של השחקן. אתה מקבל את צילומי המסך האחרונים "
           "(הישן ראשון, 2 שניות ביניהם). תן טיפ אחד קצר, ספציפי ומעשי על מה שבאמת רואים עכשיו: הגנה בזמן "
           "בנייה, גובה, חיים/מגן וריפוי, חומרים, מיקום מול הסערה, בחירת נשק לטווח, מיקום הכוונת ופרי-פייר, צדדים חשופים. "
           "עד 12 מילים, בציווי, בעברית, בלי פתיח ובלי אימוג'ים. אם הצילומים אינם משחק חי (תפריטים, לובי, טעינה, "
           "צפייה, אפליקציה אחרת) או שאין משהו מועיל, ענה בדיוק NONE. לעולם אל תנחש מה שלא רואים."),
}
PROMPT = {"en": "Screenshots above. One tip, or NONE.", "he": "הצילומים למעלה. טיפ אחד, או NONE."}


def clean_tip(text: str) -> str | None:
    t = (text or "").strip().strip('"').strip()
    if not t or t.upper().startswith("NONE") or t.upper() == "NONE.":
        return None
    t = " ".join(t.split())
    return t[:160]


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


class LiveCoach(QObject):
    tip = Signal(str)
    state_changed = Signal(bool)
    stopped_with_error = Signal(str)  # i18n key

    def __init__(self, settings_provider, service_factory, db, *, gemini_ready=lambda: True,
                 source_override: str | None = None, work_root: Path | None = None):
        super().__init__()
        self._settings = settings_provider
        self._service_factory = service_factory
        self._gemini_ready = gemini_ready
        self.db = db
        self._source_override = source_override  # "test" in automated tests only
        self._work_root = work_root
        self.capture: FrameCapture | None = None
        self.busy = False
        self.tips_shown = 0
        self.last_error: str | None = None
        self._service = None
        self._started_at = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._watch = QTimer(self)  # restarts the screenshot capture quickly if Windows cut it off
        self._watch.setInterval(2000)
        self._watch.timeout.connect(lambda: self.capture.ensure_running() if self.capture else None)

    @property
    def active(self) -> bool:
        return self.capture is not None

    def block_reason(self) -> str | None:
        s = self._settings()
        if not s.live.acknowledged:
            return "live.need_ack"
        if not self._gemini_ready():
            return "live.need_gemini"
        if usage_tracker.live_requests_today(self.db) >= s.live.max_tips_per_day:
            return "live.err_daily_limit"
        return None

    def start(self) -> bool:
        if self.active:
            return True
        reason = self.block_reason()
        if reason:
            self.last_error = reason
            self.stopped_with_error.emit(reason)
            return False
        s = self._settings()
        try:
            ffmpeg = find_ffmpeg(s.ffmpeg_path)
            folder = Path(tempfile.mkdtemp(prefix="fac_live_", dir=self._work_root))
            self.capture = FrameCapture(ffmpeg, folder, source=self._source_override or "ddagrab",
                                        monitor_index=s.recording.monitor_index)
            self.capture.start()
            self._service = self._service_factory()
        except Exception as e:  # ffmpeg missing, no key...
            log.warning("Live coach could not start: %s", e)
            self._cleanup()
            key = getattr(e, "i18n_key", "live.err_start")
            self.last_error = key
            self.stopped_with_error.emit(key)
            return False
        self.last_error = None
        self.tips_shown = 0
        self._started_at = time.monotonic()
        self._timer.start(s.live.interval_s * 1000)
        self._watch.start()
        self.state_changed.emit(True)
        return True

    def stop(self) -> None:
        if not self.active:
            return
        self._cleanup()
        self.state_changed.emit(False)

    def toggle(self) -> None:
        self.stop() if self.active else self.start()

    def _cleanup(self) -> None:
        self._timer.stop()
        self._watch.stop()
        if self.capture is not None:
            self.capture.stop()
        self.capture = None
        self._service = None

    def _fail(self, key: str) -> None:
        self.last_error = key
        self.stop()
        self.stopped_with_error.emit(key)

    def request_now(self) -> None:
        """Ask for a tip immediately (also used by the timer)."""
        self._on_timer()

    def _on_timer(self) -> None:
        if not self.active or self.busy:
            return
        s = self._settings()
        if not s.live.acknowledged:  # turned off in Settings meanwhile
            self._fail("live.need_ack")
            return
        self.capture.ensure_running()
        if usage_tracker.live_requests_today(self.db) >= s.live.max_tips_per_day:
            self._fail("live.err_daily_limit")
            return
        fresh_after = time.time() - (s.live.frames * FRAME_EVERY_S + 8)
        paths = [p for p in self.capture.latest(s.live.frames) if _mtime(p) >= fresh_after]  # never old screens
        self.capture.prune(keep=s.live.frames + 2)
        if len(paths) < 2:
            return  # not enough fresh screenshots yet
        try:
            frames = [p.read_bytes() for p in paths]
        except OSError:
            return
        lang = s.language.value if s.language.value in SYSTEM else "en"
        service, model = self._service, s.gemini.model
        self.busy = True
        run_task(lambda: service.live_tip(frames, SYSTEM[lang], PROMPT[lang]),
                 lambda res: self._done(res, model), lambda err: self._failed(err, model))

    def _done(self, res, model: str) -> None:
        self.busy = False
        usage_tracker.record(self.db, model=model, kind="live", success=True, prompt_tokens=res.prompt_tokens,
                             output_tokens=res.output_tokens)
        text = clean_tip(res.text)
        if text and self.active:
            self.tips_shown += 1
            self.tip.emit(text)

    def _failed(self, err: Exception, model: str) -> None:
        self.busy = False
        key = getattr(err, "i18n_key", None) or classify(err).i18n_key
        usage_tracker.record(self.db, model=model, kind="live", success=False, error_code=key)
        log.warning("Live tip failed: %s", key)
        if key in FATAL_KEYS:
            self._fail(key)
        else:
            self.last_error = key  # transient (busy, timeout): the next interval tries again


__all__ = ["LiveCoach", "clean_tip", "FRAME_EVERY_S"]
