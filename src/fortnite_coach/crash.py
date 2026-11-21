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


def show_startup_error(exc: Exception, log_path: str) -> None:
    from fortnite_coach.logging_setup import redact

    detail = redact(f"{type(exc).__name__}: {exc}")[:400]
    _show_dialog(
        "The app could not start.\n\n"
        f"{detail}\n\n"
        f"Details: {log_path}\n\n"
        "האפליקציה לא הצליחה להיפתח. צלם את ההודעה הזו ושלח אותה."
    )


def install_excepthook(log_path: str, show_dialog: bool = True) -> None:
    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("Unhandled exception:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
        if show_dialog:
            from fortnite_coach.logging_setup import redact

            detail = redact(f"{exc_type.__name__}: {exc}")[:300]
            _show_dialog(
                "An unexpected error occurred. The app keeps running.\n"
                f"{detail}\n\nDetails were saved to:\n{log_path}\n\n"
                "אירעה שגיאה לא צפויה. צלם את ההודעה ושלח אותה."
            )

    sys.excepthook = hook
