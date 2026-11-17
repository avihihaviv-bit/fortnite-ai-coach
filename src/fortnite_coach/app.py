"""Application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from fortnite_coach import APP_ID, APP_NAME, __version__
from fortnite_coach.config.paths import AppPaths, resource_path
from fortnite_coach.ui.theme import stylesheet


def create_app(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ID)
    app.setApplicationVersion(__version__)
    icon = resource_path("assets/app.png")
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    font = QFont("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())
    return app


def _arg_value(argv: list[str], flag: str) -> str | None:
    if flag in argv:
        i = argv.index(flag)
        return argv[i + 1] if i + 1 < len(argv) else None
    return None


def run(argv: list[str]) -> int:
    if "--self-test" in argv:
        from fortnite_coach.selftest import main as self_test

        return self_test(_arg_value(argv, "--out"))

    import logging

    from fortnite_coach.crash import install_excepthook
    from fortnite_coach.logging_setup import setup_logging

    paths = AppPaths.default().ensure()
    log_file = setup_logging(paths.logs_dir)
    install_excepthook(str(log_file))
    log = logging.getLogger("fortnite_coach")
    app = create_app(argv)

    from fortnite_coach.single_instance import SingleInstance

    instance = SingleInstance()
    if instance.notify_running_instance():
        log.info("Another instance is running; asked it to come to the front")
        return 0
    instance.listen()

    from fortnite_coach.db.engine import Database
    from fortnite_coach.db.repositories.knowledge_repo import seed_builtin
    from fortnite_coach.db.repositories.profile_repo import get_or_create_profile
    from fortnite_coach.ui.main_window import MainWindow

    log.info("Starting %s %s (frozen=%s)", APP_NAME, __version__, bool(getattr(sys, "frozen", False)))
    db = Database(paths.database).init()
    get_or_create_profile(db)
    seed_builtin(db)
    window = MainWindow(db, paths)
    instance.activated.connect(window.bring_to_front)
    window.show()
    try:
        return app.exec()
    finally:
        instance.close()
        db.close()
        log.info("Exited cleanly")
