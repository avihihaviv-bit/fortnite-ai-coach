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


def _replace_stuck_instance() -> bool:
    """Ask, then end the other (stuck) copy of the app. True = continue starting."""
    import os
    import subprocess

    from PySide6.QtWidgets import QMessageBox

    answer = QMessageBox.question(
        None, APP_NAME,
        "Fortnite AI Coach is already running in the background but is not responding.\n"
        "Close it and start again?\n\n"
        "האפליקציה כבר פתוחה ברקע אבל לא מגיבה. לסגור אותה ולפתוח מחדש?")
    if answer != QMessageBox.StandardButton.Yes:
        return False
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        exe = os.path.basename(sys.executable)
        subprocess.run(["taskkill", "/F", "/IM", exe, "/FI", f"PID ne {os.getpid()}"],
                       capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        import time

        time.sleep(1.0)
    return True


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
    app.setQuitOnLastWindowClosed(False)  # the tray keeps the app alive; "Quit" exits

    from fortnite_coach.single_instance import SingleInstance

    instance = SingleInstance()
    if instance.notify_running_instance():
        if instance.last_ack:
            log.info("Another instance is running; asked it to come to the front")
            return 0
        # The other copy is running but does not answer (stuck in the background): don't just exit silently.
        log.warning("Another instance is running but not responding")
        if not _replace_stuck_instance():
            return 0
    instance.listen()

    from fortnite_coach.db.engine import Database
    from fortnite_coach.db.repositories.knowledge_repo import seed_builtin
    from fortnite_coach.db.repositories.profile_repo import get_or_create_profile
    from fortnite_coach.ui.main_window import MainWindow

    log.info("Starting %s %s (frozen=%s)", APP_NAME, __version__, bool(getattr(sys, "frozen", False)))
    try:
        db = Database(paths.database).init()
        get_or_create_profile(db)
        seed_builtin(db)
        window = MainWindow(db, paths)
    except Exception as e:
        # Never stay running without a window: a hidden process would make every later launch exit silently.
        import traceback

        from fortnite_coach.crash import show_startup_error

        log.critical("Startup failed:\n%s", traceback.format_exc())
        instance.close()
        show_startup_error(e, str(log_file))
        return 1
    window.quit_on_close = True
    instance.activated.connect(window.bring_to_front)
    window.show()
    try:
        return app.exec()
    finally:
        instance.close()
        db.close()
        log.info("Exited cleanly")
