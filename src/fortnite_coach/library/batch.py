"""Analyze several clips one after another on a worker thread (prepare first, then confirm, then send)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal

from fortnite_coach.coaching import pipeline
from fortnite_coach.core.errors import CoachError, OperationCancelledError, UsageLimitExceededError
from fortnite_coach.core.game_modes import AnalysisDepth, GameMode
from fortnite_coach.db.repositories import session_repo
from fortnite_coach.video.importer import import_video
from fortnite_coach.workers.task import run_task


@dataclass
class Prepared:
    path: str
    request: pipeline.AnalysisRequest | None = None
    to_send: int = 0
    cached: int = 0
    error: str | None = None  # i18n key when the file could not be read


@dataclass
class BatchItemResult:
    path: str
    report_id: int | None = None
    error: str | None = None
    failed_segments: int = 0


@dataclass
class BatchResult:
    items: list[BatchItemResult] = field(default_factory=list)
    stopped_reason: str | None = None  # i18n key when the batch stopped early (limit, fatal error, cancel)


def prepare(db, paths, settings, clip_paths: list[str], mode: GameMode, depth: AnalysisDepth, language: str,
            progress=lambda *_: None, cancel: threading.Event | None = None) -> list[Prepared]:
    """Read metadata + fingerprint of each clip (local only, no requests) and plan its requests."""
    out = []
    for i, path in enumerate(clip_paths, 1):
        if cancel is not None and cancel.is_set():
            raise OperationCancelledError()
        progress("clips.preparing", i, len(clip_paths))
        try:
            v = import_video(path, paths.frames_dir, settings.ffprobe_path)
        except CoachError as e:
            out.append(Prepared(path, error=e.i18n_key))
            continue
        except Exception:
            out.append(Prepared(path, error="video.err_unreadable"))
            continue
        m = v.meta
        vid = session_repo.upsert_video(db, session_repo.VideoInfo(
            path=m.path, fingerprint=v.fingerprint, size_bytes=m.size_bytes, duration_s=m.duration_s,
            width=m.width, height=m.height, fps=m.fps, codec=m.codec))
        req = pipeline.AnalysisRequest(video_id=vid, video_path=m.path, fingerprint=v.fingerprint,
                                       duration_s=m.duration_s, mode=mode, depth=depth, focus=[], language=language)
        p = pipeline.plan(db, settings, req)
        out.append(Prepared(path, req, p.to_send, p.cached))
    return out


FATAL_STOP = {"gemini.err_key", "gemini.err_no_free_quota", "gemini.err_quota_daily", "gemini.err_region",
              "gemini.err_model", "gemini.err_no_key"}


def analyze_all(db, paths, settings, service, items: list[Prepared], progress=lambda *_: None,
                cancel: threading.Event | None = None) -> BatchResult:
    res = BatchResult()
    todo = [p for p in items if p.request is not None]
    for i, p in enumerate(todo, 1):
        if cancel is not None and cancel.is_set():
            res.stopped_reason = "error.cancelled"
            break
        progress("clips.analyzing", i, len(todo))
        try:
            o = pipeline.run_analysis(db, paths, settings, service, p.request, cancel=cancel)
            res.items.append(BatchItemResult(p.path, o.report_id, failed_segments=o.failed_segments))
        except OperationCancelledError:
            res.stopped_reason = "error.cancelled"
            break
        except UsageLimitExceededError:
            res.items.append(BatchItemResult(p.path, error="error.usage_limit"))
            res.stopped_reason = "error.usage_limit"
            break
        except Exception as e:
            key = getattr(e, "i18n_key", "error.generic")
            res.items.append(BatchItemResult(p.path, error=key))
            if key in FATAL_STOP:
                res.stopped_reason = key
                break
    return res


class BatchJob(QObject):
    progress = Signal(str, int, int)
    prepared = Signal(object)   # list[Prepared]
    finished = Signal(object)   # BatchResult
    failed = Signal(object)

    def __init__(self, db, paths, settings):
        super().__init__()
        self.db, self.paths, self.settings = db, paths, settings
        self._cancel = threading.Event()
        self.running = False
        self.items: list[Prepared] = []

    def cancel(self) -> None:
        self._cancel.set()

    def start_prepare(self, clip_paths, mode, depth, language) -> None:
        self.running = True
        run_task(lambda: prepare(self.db, self.paths, self.settings, clip_paths, mode, depth, language,
                                 self.progress.emit, self._cancel), self._prepared, self._fail)

    def _prepared(self, items) -> None:
        self.running = False
        self.items = items
        self.prepared.emit(items)

    def start_analyze(self, service) -> None:
        self.running = True
        run_task(lambda: analyze_all(self.db, self.paths, self.settings, service, self.items, self.progress.emit,
                                     self._cancel), self._done, self._fail)

    def _done(self, res) -> None:
        self.running = False
        self.finished.emit(res)

    def _fail(self, err) -> None:
        self.running = False
        self.failed.emit(err)
