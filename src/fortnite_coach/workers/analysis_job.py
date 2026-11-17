"""Runs the analysis pipeline on a worker thread with progress + cancel, delivering results to the UI thread."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from fortnite_coach.coaching.pipeline import AnalysisRequest, run_analysis
from fortnite_coach.workers.task import run_task


class AnalysisJob(QObject):
    progress = Signal(str, int, int)   # i18n step key, current, total
    finished = Signal(object)          # AnalysisOutcome
    failed = Signal(object)            # Exception

    def __init__(self, db, paths, settings, service, request: AnalysisRequest):
        super().__init__()
        self._args = (db, paths, settings, service, request)
        self._cancel = threading.Event()
        self.running = False

    def start(self) -> None:
        self.running = True
        db, paths, settings, service, req = self._args
        run_task(lambda: run_analysis(db, paths, settings, service, req, progress=self.progress.emit, cancel=self._cancel),
                 self._done, self._fail)

    def cancel(self) -> None:
        self._cancel.set()

    def _done(self, outcome) -> None:
        self.running = False
        self.finished.emit(outcome)

    def _fail(self, err) -> None:
        self.running = False
        self.failed.emit(err)
