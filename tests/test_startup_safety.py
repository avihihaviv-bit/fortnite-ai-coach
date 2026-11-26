"""The app must always open (or exit with a visible reason), whatever Windows Credential Manager does."""

import keyring
import pytest
from keyring.backend import KeyringBackend

from fortnite_coach.ai.key_store import KeyStore, KeyStoreError


class BrokenKeyring(KeyringBackend):
    priority = 1

    def get_password(self, service, username):
        raise OSError("Windows credential error 1312 (TEST DATA)")  # not a KeyringError

    def set_password(self, service, username, password):
        raise OSError("Windows credential error (TEST DATA)")

    def delete_password(self, service, username):
        raise OSError("TEST DATA")


def test_key_store_survives_raw_windows_errors():
    previous = keyring.get_keyring()
    keyring.set_keyring(BrokenKeyring())
    try:
        ks = KeyStore()
        assert ks.load() is None and not ks.has_key()
        with pytest.raises(KeyStoreError):
            ks.save("AIza" + "Q" * 35)
        with pytest.raises(KeyStoreError):
            ks.delete()
    finally:
        keyring.set_keyring(previous)


def test_window_opens_even_if_the_key_cannot_be_read(qtbot, tmp_path):
    from fortnite_coach.app import create_app
    from fortnite_coach.config.paths import AppPaths
    from fortnite_coach.db.engine import Database
    from fortnite_coach.ui.main_window import MainWindow

    create_app([])
    previous = keyring.get_keyring()
    keyring.set_keyring(BrokenKeyring())
    try:
        paths = AppPaths(tmp_path / "h").ensure()
        db = Database(paths.database).init()
        w = MainWindow(db, paths, recording_source="test")
        qtbot.addWidget(w)
        assert w.gemini_status().name == "NOT_CONFIGURED"
        w._quitting = True
        db.close()
    finally:
        keyring.set_keyring(previous)


def test_failed_optional_startup_step_does_not_block_the_window(qtbot, tmp_path, monkeypatch):
    from fortnite_coach.app import create_app
    from fortnite_coach.config.paths import AppPaths
    from fortnite_coach.db.engine import Database
    from fortnite_coach.ui import main_window

    create_app([])

    def boom(self):
        raise RuntimeError("TEST DATA")

    monkeypatch.setattr(main_window.MainWindow, "refresh_data", boom)
    paths = AppPaths(tmp_path / "h").ensure()
    db = Database(paths.database).init()
    w = main_window.MainWindow(db, paths, recording_source="test")
    qtbot.addWidget(w)
    assert "data" in w.startup_errors
    w._quitting = True
    db.close()


def test_startup_failure_exits_with_a_message(monkeypatch, tmp_path):
    """A crash while building the window must end the process (no hidden copy blocking later launches)."""
    from fortnite_coach import app as appmod
    from fortnite_coach import crash
    from fortnite_coach.ui import main_window

    import sys

    monkeypatch.setattr(sys, "excepthook", sys.excepthook)  # run() installs its own hook; restore it afterwards
    shown = []
    monkeypatch.setattr(crash, "_show_dialog", shown.append)
    monkeypatch.setattr(main_window, "MainWindow", lambda *a, **k: (_ for _ in ()).throw(ValueError("TEST DATA boom")))
    monkeypatch.setattr("fortnite_coach.single_instance.SingleInstance.notify_running_instance", lambda self, *a: False)
    assert appmod.run(["app"]) == 1
    assert shown and "could not start" in shown[0] and "TEST DATA boom" in shown[0]


def test_connection_test_uses_short_timeouts_and_accepts_rate_limit():
    from fortnite_coach.ai.gemini_connection_test import REQUEST_TIMEOUT_S, test_connection
    from fortnite_coach.ai.gemini_service import GeminiService
    from tests.fake_gemini import FakeAPIError, FakeClient

    client = FakeClient()
    seen = {}
    orig = client.models.generate_content

    def gen(model, contents, config):
        seen["timeout"] = config.http_options.timeout if config.http_options else None
        raise FakeAPIError(429, "RESOURCE_EXHAUSTED: requests per minute TEST DATA")

    client.models.generate_content = gen
    svc = GeminiService(lambda: "k", "gemini-2.5-flash", max_retries=3, client_factory=lambda k, t: client)
    svc._sleep = lambda s: None
    res = test_connection(svc)
    assert res.ok  # rate limited = key and model work
    assert seen["timeout"] == REQUEST_TIMEOUT_S * 1000
    assert svc.max_retries == 1


def test_stuck_connection_test_gives_up(qtbot, tmp_path):
    import threading

    from fortnite_coach.app import create_app
    from fortnite_coach.config.paths import AppPaths
    from fortnite_coach.db.engine import Database
    from fortnite_coach.ui.main_window import MainWindow
    from fortnite_coach.workers.task import wait_all
    from tests.fake_gemini import FakeClient

    create_app([])
    release = threading.Event()
    client = FakeClient()
    client.models.list = lambda config=None: (release.wait(10), [])[1]  # Google never answers (TEST DATA)
    paths = AppPaths(tmp_path / "h").ensure()
    db = Database(paths.database).init()
    w = MainWindow(db, paths, recording_source="test", client_factory=lambda k, t: client)
    qtbot.addWidget(w)
    w.TEST_GIVE_UP_MS = 300
    w.set_language("en")
    w.settings_page.key_edit.setText("AIza" + "T" * 35)
    w.settings_page.save_key_btn.click()
    w.settings_page.test_btn.click()
    assert w.settings_page.testing
    qtbot.waitUntil(lambda: not w.settings_page.testing, timeout=5000)
    assert w.settings.gemini.last_test_error == "gemini.err_test_timeout"
    assert "did not answer" in w.settings_page.test_result.text()
    release.set()
    wait_all()
    assert w.settings.gemini.last_test_error == "gemini.err_test_timeout"  # the late answer was ignored
    w._quitting = True
    db.close()


def test_settings_save_themselves_and_survive_redraws(qtbot, tmp_path):
    """User-facing trap: edits were lost when the card redrew itself before Save was clicked."""
    from fortnite_coach.app import create_app
    from fortnite_coach.config.paths import AppPaths
    from fortnite_coach.db.engine import Database
    from fortnite_coach.db.repositories import settings_repo
    from fortnite_coach.ui.main_window import MainWindow

    create_app([])
    paths = AppPaths(tmp_path / "h").ensure()
    db = Database(paths.database).init()
    before = settings_repo.load_settings(db)
    w = MainWindow(db, paths, recording_source="test")
    qtbot.addWidget(w)
    sp = w.settings_page
    # opening the app must not change anything (no half-loaded saves)
    after_open = settings_repo.load_settings(db)
    assert after_open.live == before.live and after_open.recording == before.recording
    sp.limit_spin.setValue(37)
    sp.refresh_cards()
    sp._render_gemini()                      # redraw (happens every second during a test)
    assert sp.limit_spin.value() == 37 and settings_repo.load_settings(db).limits.max_requests_per_day == 37
    sp.auto_analyze.setChecked(True)
    assert settings_repo.load_settings(db).recording.auto_analyze
    sp.hk_toggle.setText("F3")               # clashes with Live: hotkey kept, nothing else lost
    assert settings_repo.load_settings(db).recording.hotkey_toggle == "F2"
    card = sp.live_card
    card.interval.setValue(25)
    assert settings_repo.load_settings(db).live.interval_s == 25
    w._quitting = True
    db.close()
