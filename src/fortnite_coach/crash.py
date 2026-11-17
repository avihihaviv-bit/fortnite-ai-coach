"""Unhandled exceptions are logged and shown to the user instead of vanishing silently."""

from __future__ import annotations

import logging
import sys
import traceback

log = logging.getLogger("fortnite_coach.crash")


def _show_dialog(text: str) -> None:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is not None:
            QMessageBox.critical(None, "Fortnite AI Coach", text)
    except Exception:  # pragma: no cover - never raise from the crash handler
        pass


def install_excepthook(log_path: str, show_dialog: bool = True) -> None:
    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("Unhandled exception:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
        if show_dialog:
            _show_dialog(
                "An unexpected error occurred. The app may need to restart.\n"
                f"Details were saved to:\n{log_path}\n\n"
                "אירעה שגיאה לא צפויה. הפרטים נשמרו בקובץ היומן שלמעלה."
            )

    sys.excepthook = hook
