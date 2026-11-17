"""Full user flow with a fake Gemini client (TEST DATA). No real key, no network."""

import pytest

from fortnite_coach.ai.status import GeminiStatus
from fortnite_coach.app import create_app
from fortnite_coach.config.paths import AppPaths
from fortnite_coach.db.engine import Database
from fortnite_coach.db.repositories import report_repo
from fortnite_coach.i18n.translator import get_translator
from fortnite_coach.workers.task import wait_all
from tests.fake_gemini import FakeClient, segment_json

FAKE_KEY = "AIza" + "U" * 35  # TEST DATA


@pytest.fixture
def setup(qtbot, tmp_path):
    from fortnite_coach.ui.main_window import MainWindow

    create_app([])
    paths = AppPaths(tmp_path / "home").ensure()
    db = Database(paths.database).init()
    client = FakeClient(responses=[segment_json("00:02")])
    w = MainWindow(db, paths, recording_source="test", client_factory=lambda k, t: client)
    w.set_language("en")
    qtbot.addWidget(w)
    w.show()
    yield w, client, qtbot
    wait_all()
    w.quit_on_close = False
    w._quitting = True
    db.close()
    get_translator().set_language("he")


def connect(w, qtbot):
    sp = w.settings_page
    sp.key_edit.setText(FAKE_KEY)
    sp.save_key_btn.click()
    assert w.gemini_status() is GeminiStatus.CONFIGURED_UNTESTED
    sp.test_btn.click()
    qtbot.waitUntil(lambda: not sp.testing, timeout=10000)
    assert w.gemini_status() is GeminiStatus.CONNECTED
    assert "Connected" in sp.test_result.text()


def load(w, qtbot, video):
    page = w.pages["gameplay"]
    page.load_path(str(video))
    qtbot.waitUntil(lambda: not page.loading, timeout=20000)
    return page


def test_connection_test_flow(setup):
    w, client, qtbot = setup
    connect(w, qtbot)
    assert "Gemini connected" in w.sidebar.status.text()
    w.settings_page.key_edit.setText("AIza" + "V" * 35)  # a new key must be tested again
    w.settings_page.save_key_btn.click()
    assert w.gemini_status() is GeminiStatus.CONFIGURED_UNTESTED


def test_full_analysis_from_the_ui(setup, sample_video, monkeypatch):
    w, client, qtbot = setup
    connect(w, qtbot)
    page = load(w, qtbot, sample_video)
    assert page.analyze_btn.isEnabled()
    asked = []
    monkeypatch.setattr(page, "confirm", lambda title, text: asked.append(text) or True)
    page.analyze_btn.click()
    assert asked and "Free Tier" in asked[0] and "Requests to send: 1" in asked[0]
    qtbot.waitUntil(lambda: page.job is not None and not page.job.running, timeout=30000)
    wait_all()
    # report opened in History with XP banner
    assert w.current_key == "history"
    hist = w.pages["history"]
    assert hist.current_report is not None and "+50 XP" in hist.banner_text
    assert hist.list.count() == 1 and len(hist._cards) == 2  # 1 good play + 1 mistake
    # levels everywhere
    assert report_repo.levels(w.db).overall.total_xp == 50
    assert w.pages["dashboard"].overall_level.info.total_xp == 50
    editing = w.pages["editing"]
    assert editing.level_bar.info.total_xp == 50 and editing.findings_box.isVisibleTo(editing)
    assert "Level 1" in w.pages["dashboard"].overall_level.level_label.text()
    # delete the session -> XP gone
    monkeypatch.setattr(hist, "confirm", lambda *a: True)
    hist.delete_btn.click()
    assert report_repo.levels(w.db).overall.total_xp == 0
    assert w.pages["dashboard"].overall_level.info.total_xp == 0


def test_declining_confirmation_sends_nothing(setup, sample_video, monkeypatch):
    w, client, qtbot = setup
    connect(w, qtbot)
    page = load(w, qtbot, sample_video)
    monkeypatch.setattr(page, "confirm", lambda *a: False)
    page.analyze_btn.click()
    assert page.job is None and client.uploads == 0 and not client.generate_calls


def test_fortnite_running_blocks_analysis(setup, sample_video, monkeypatch):
    w, client, qtbot = setup
    connect(w, qtbot)
    page = load(w, qtbot, sample_video)
    from fortnite_coach.recording import process_guard

    monkeypatch.setattr(process_guard, "is_fortnite_running", lambda: True)
    monkeypatch.setattr(page, "confirm", lambda *a: pytest.fail("must not ask"))
    page.analyze_btn.click()
    assert "Fortnite is running" in page.analyze_reason.text() and client.uploads == 0


def test_without_key_analyze_stays_disabled(setup, sample_video):
    w, client, qtbot = setup
    page = load(w, qtbot, sample_video)
    assert not page.analyze_btn.isEnabled()
    assert "API key not configured" in page.analyze_reason.text()
    assert w.pages["dashboard"].overall_level.info.total_xp == 0
    assert "0 XP" in w.pages["dashboard"].overall_level.xp_label.text()


def test_tray_controls_recording_and_close_keeps_running(setup):
    w, client, qtbot = setup
    tray = w.tray
    tray.a_start.trigger()
    assert w.recording.is_recording and not tray.a_start.isEnabled() and tray.a_stop.isEnabled()
    qtbot.wait(1500)
    tray.a_stop.trigger()
    assert not w.recording.is_recording
    if tray.available:
        w.close()
        assert w.isHidden() and not w._quitting  # still alive in the tray
        tray.open_requested.emit()
        assert w.isVisible()
