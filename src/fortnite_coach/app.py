"""Application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from fortnite_coach import APP_ID, APP_NAME, __version__
from fortnite_coach.config.paths import AppPaths
from fortnite_coach.ui.theme import stylesheet


def create_app(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ID)
    app.setApplicationVersion(__version__)
    font = QFont("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())
    return app


def run(argv: list[str]) -> int:
    AppPaths.default().ensure()
    app = create_app(argv)
    from fortnite_coach.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()
