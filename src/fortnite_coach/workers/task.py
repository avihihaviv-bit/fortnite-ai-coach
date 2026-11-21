"""Run a function on a worker thread and deliver the result on the UI thread.

Threads exist only while a user-started job runs; nothing polls in the background.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(object)


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], Any], signals: _Signals):
        super().__init__()
        self.fn, self.signals = fn, signals
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as e:  # delivered to the UI as an error, never swallowed
            self.signals.failed.emit(e)
        else:
            self.signals.done.emit(result)


_alive: set[_Signals] = set()


def run_task(fn: Callable[[], Any], on_done: Callable[[Any], None], on_error: Callable[[Exception], None]) -> None:
    signals = _Signals()
    _alive.add(signals)

    def _finish(cb, value):
        _alive.discard(signals)
        cb(value)

    signals.done.connect(lambda r: _finish(on_done, r))
    signals.failed.connect(lambda e: _finish(on_error, e))
    pool = QThreadPool.globalInstance()
    if pool.maxThreadCount() < 8:  # a slow job (hardware check, clip scan) must never queue a quick one
        pool.setMaxThreadCount(8)
    pool.start(_Task(fn, signals))


def wait_all(timeout_ms: int = 30000) -> bool:
    """Used by tests and on shutdown."""
    return QThreadPool.globalInstance().waitForDone(timeout_ms)
