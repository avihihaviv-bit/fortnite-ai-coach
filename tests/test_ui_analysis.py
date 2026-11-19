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


def test_analysis_creates_plan_and_exercise_can_be_completed(setup, sample_video, monkeypatch):
    w, client, qtbot = setup
    connect(w, qtbot)
    page = load(w, qtbot, sample_video)
    monkeypatch.setattr(page, "confirm", lambda *a: True)
    page.analyze_btn.click()
    qtbot.waitUntil(lambda: page.job is not None and not page.job.running, timeout=30000)
    wait_all()
    tp = w.pages["training_plan"]
    assert tp.plan is not None and len(tp.cards) >= 2
    assert tp.cards[0].ex.template_id == "warmup_mechanics"
    edit = [c for c in tp.cards if c.ex.template_id == "edit_reset_drill"]
    assert edit, [c.ex.template_id for c in tp.cards]  # TEST DATA mistake EDIT_EXPOSED_AFTER -> its drill
    edit[0].done_btn.click()
    assert "Done ×1" in tp.cards[[c.ex.template_id for c in tp.cards].index("edit_reset_drill")].count.text()


def test_progress_page_after_two_analyses(setup, sample_video, tmp_path, monkeypatch):
    import shutil

    w, client, qtbot = setup
    connect(w, qtbot)
    from tests.fake_gemini import segment_json

    client._responses = [segment_json("00:02", score=40), segment_json("00:03", score=65)]
    second = tmp_path / "second.mp4"
    shutil.copy(sample_video, second)
    with open(second, "ab") as f:  # different fingerprint = a different recording
        f.write(b"\0")
    for video in (sample_video, second):
        page = load(w, qtbot, video)
        monkeypatch.setattr(page, "confirm", lambda *a: True)
        page.analyze_btn.click()
        qtbot.waitUntil(lambda: page.job is not None and not page.job.running, timeout=30000)
        wait_all()
    prog = w.pages["progress"]
    assert len(prog.points) == 2 and prog.compare_card.isVisibleTo(prog)
    prog.skill_combo.setCurrentIndex(prog.skill_combo.findData("editing"))
    assert len(prog.score_chart.points) == 2 and [p[1] for p in prog.score_chart.points] == [40, 65]
    assert "40 → 65" in prog.compare_result.text()
    assert prog.table.rowCount() >= 1
    assert "XP" in w.pages["dashboard"].weekly_label.text() or w.pages["dashboard"].weekly_label.isHidden() is False


def test_settings_usage_knowledge_about_cards(setup, monkeypatch):
    w, client, qtbot = setup
    sp = w.settings_page
    assert not sp.knowledge_card.update_btn.isEnabled()  # no key -> no knowledge request possible
    assert "Needs a connected Gemini key" in sp.knowledge_card.feedback_label.text()
    assert "18 built-in fundamentals" in sp.knowledge_card.summary.text() or "built-in" in sp.knowledge_card.summary.text()
    connect(w, qtbot)
    assert sp.knowledge_card.update_btn.isEnabled()
    assert "Today: 0 of" in sp.usage_card.limit_label.text()
    assert "Live Coach" in sp.about_card.privacy.text() and "not available" in sp.about_card.privacy.text()
    sp.about_card.selftest_btn.click()
    qtbot.waitUntil(lambda: not sp.about_card.running, timeout=30000)
    assert "Everything required works" in sp.about_card.result.text()


def test_onboarding_checklist_follows_real_state(setup, sample_video, monkeypatch):
    w, client, qtbot = setup
    ob = w.onboarding
    assert ob.isVisibleTo(w.pages["dashboard"]) and not any(ob.done.values())
    assert "0/6" in ob.title_label.text()
    connect(w, qtbot)
    assert ob.done["key"] and ob.done["test"] and not ob.done["video"]
    load(w, qtbot, sample_video)
    assert ob.done["video"]
    ob.rows["exercise"][2].click()  # "Go" opens the right page
    assert w.current_key == "training_plan"


def test_key_paste_button_and_live_hint(setup):
    from PySide6.QtWidgets import QApplication

    w, client, qtbot = setup
    sp = w.settings_page
    QApplication.clipboard().setText(f'  "{FAKE_KEY}"\n')  # TEST DATA with copy noise
    sp.paste_key_btn.click()
    assert sp.key_edit.text() == FAKE_KEY
    assert "Looks like a Gemini key" in sp.key_hint.text()
    assert FAKE_KEY not in sp.key_hint.text()  # the hint never shows the key
    sp.key_edit.setText("hello world!!! not a key at all #")
    assert "characters" in sp.key_hint.text()


def test_help_page_uses_configured_hotkeys(setup):
    w, client, qtbot = setup
    w.navigate("help")
    texts = " ".join(body.text() for _, body, _ in w.pages["help"].cards)
    assert "Ctrl+Shift+F9" in texts and "Windowed Fullscreen" in texts and "aistudio.google.com" in texts
