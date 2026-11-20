"""Phase 5 UI: API key field, honest 'not configured' messages, video import, in-app recording."""

import time

import pytest

from fortnite_coach.ai.key_store import KeyStore
from fortnite_coach.ai.status import GeminiStatus
from fortnite_coach.app import create_app
from fortnite_coach.config.paths import AppPaths
from fortnite_coach.db.engine import Database
from fortnite_coach.db.repositories import session_repo
from fortnite_coach.i18n.translator import get_translator
from fortnite_coach.workers.task import wait_all

FAKE_KEY = "AIza" + "Q" * 35  # TEST DATA: not a real key


@pytest.fixture
def win(qtbot, tmp_path):
    from fortnite_coach.ui.main_window import MainWindow

    create_app([])
    get_translator().set_language("en")
    paths = AppPaths(tmp_path / "home").ensure()
    db = Database(paths.database).init()
    w = MainWindow(db, paths, recording_source="test")
    w.set_language("en")  # the window loads the saved language (Hebrew by default)
    qtbot.addWidget(w)
    w.show()
    yield w
    if w.recording.is_recording:
        w.recording.stop()
    wait_all()
    db.close()
    get_translator().set_language("he")


def test_no_key_message_everywhere(win):
    assert win.gemini_status() is GeminiStatus.NOT_CONFIGURED
    assert "API key not configured" in win.sidebar.status.text()
    sp = win.settings_page
    assert "API key not configured" in sp.gemini_status.text()
    assert "No key yet" in sp.gemini_info.text()
    assert "aistudio.google.com" in sp.gemini_guide.text()


def test_key_field_is_masked_and_toggles(win):
    sp = win.settings_page
    from PySide6.QtWidgets import QLineEdit

    assert sp.key_edit.echoMode() == QLineEdit.EchoMode.Password
    sp.show_key_btn.click()
    assert sp.key_edit.echoMode() == QLineEdit.EchoMode.Normal
    sp.show_key_btn.click()
    assert sp.key_edit.echoMode() == QLineEdit.EchoMode.Password


def test_save_key_updates_status_but_never_enables_fake_analysis(win, memory_keyring):
    sp = win.settings_page
    sp.key_edit.setText(FAKE_KEY)
    sp.save_key_btn.click()
    assert KeyStore().load() == FAKE_KEY
    assert sp.key_edit.text() == ""  # key does not linger in the widget
    assert FAKE_KEY not in sp.key_edit.placeholderText()  # only masked
    assert win.gemini_status() is GeminiStatus.CONFIGURED_UNTESTED
    assert "not tested" in win.sidebar.status.text()
    page = win.pages["gameplay"]
    assert page.analyze_block_reason() in ("analysis.need_video", "analysis.need_test")


def test_key_never_written_to_disk(win, tmp_path):
    sp = win.settings_page
    sp.key_edit.setText(FAKE_KEY)
    sp.save_key_btn.click()
    win.db.close()
    for f in (tmp_path / "home").rglob("*"):
        if f.is_file():
            assert FAKE_KEY.encode() not in f.read_bytes(), f


def test_invalid_key_rejected_with_message(win):
    sp = win.settings_page
    sp.key_edit.setText("not a key")
    sp.save_key_btn.click()
    assert not KeyStore().has_key()
    assert "does not look like an API key" in sp.key_feedback.text()


def test_delete_key(win, monkeypatch):
    sp = win.settings_page
    sp.key_edit.setText(FAKE_KEY)
    sp.save_key_btn.click()
    monkeypatch.setattr(sp, "confirm", lambda *a: True)
    sp.delete_key_btn.click()
    assert win.gemini_status() is GeminiStatus.NOT_CONFIGURED


def _import(win, qtbot, page, path):
    page.load_path(str(path))
    qtbot.waitUntil(lambda: not page.loading, timeout=20000)


def test_import_video_shows_metadata_and_blocks_analysis(win, qtbot, sample_video):
    page = win.pages["gameplay"]
    assert not page.video_card.isVisibleTo(page)
    _import(win, qtbot, page, sample_video)
    assert page.error_key is None
    assert page.video_card.isVisibleTo(page)
    assert page.meta_labels["resolution"][1].text() == "640×360"
    assert page.meta_labels["fps"][1].text() == "30"
    assert page.meta_labels["duration"][1].text() == "00:06"
    assert not page.thumb_labels[0].pixmap().isNull()
    assert "Will analyze 00:06 of 00:06" in page.coverage_label.text()
    assert not page.analyze_btn.isEnabled()
    assert "API key not configured" in page.analyze_reason.text()
    assert session_repo.counts(win.db)["videos"] == 1
    assert page.recent_list.count() == 1
    _import(win, qtbot, page, sample_video)  # same file again: no duplicate row
    assert session_repo.counts(win.db)["videos"] == 1


def test_import_error_is_shown(win, qtbot, tmp_path):
    page = win.pages["gameplay"]
    bad = tmp_path / "game.replay"
    bad.write_bytes(b"x")
    _import(win, qtbot, page, bad)
    assert ".replay files are not supported" in page.import_status.text()


def test_training_page_offers_only_training_modes(win):
    page = win.pages["training_sessions"]
    modes = {page.mode_combo.itemData(i) for i in range(page.mode_combo.count())}
    assert modes == {"creative_free_build", "realistic_1v1", "box_fights", "zone_wars"}
    assert win.pages["gameplay"].mode_combo.count() == 7


def test_record_from_app_then_load(win, qtbot):
    """Uses the synthetic 'test' capture source (Linux CI has no Windows screen capture)."""
    rc = win.recording
    assert rc.start()
    assert rc.is_recording and win.sidebar.rec_pill.isVisibleTo(win.sidebar)
    assert win.windowTitle().startswith("● REC")
    time.sleep(2.0)
    done = []
    rc.finished.connect(done.append)
    rc.stop()
    assert done and done[0][0].endswith("_part1.mp4")
    assert not win.sidebar.rec_pill.isVisibleTo(win.sidebar)
    page = win.pages["gameplay"]
    assert page.rec_load.isVisibleTo(page)  # not auto-processed; user loads it
    page.rec_load.click()
    qtbot.waitUntil(lambda: not page.loading, timeout=20000)
    assert page.current is not None and page.current.meta.duration_s > 1


def test_recording_settings_saved(win):
    sp = win.settings_page
    sp.res_combo.setCurrentIndex(sp.res_combo.findData("720p"))
    sp.fps_combo.setCurrentIndex(sp.fps_combo.findData(30))
    sp.hk_start.setText("Ctrl+Alt+F7")
    sp.hk_stop.setText("Ctrl+Alt+F8")
    sp.rec_save_btn.click()
    from fortnite_coach.db.repositories.settings_repo import load_settings

    rec = load_settings(win.db).recording
    assert (rec.resolution, rec.fps, rec.hotkey_start) == ("720p", 30, "Ctrl+Alt+F7")


def test_same_hotkey_for_start_and_stop_rejected(win):
    sp = win.settings_page
    sp.hk_start.setText("Ctrl+Alt+F7")
    sp.hk_stop.setText("ctrl+alt+f7")
    sp.rec_save_btn.click()
    assert "Invalid hotkeys" in sp.rec_feedback.text()


def test_hebrew_no_key_message(win):
    win.set_language("he")
    assert "מפתח API לא הוגדר" in win.sidebar.status.text()
    assert "מפתח Gemini API לא הוגדר" in win.pages["gameplay"].analyze_reason.text() or \
        win.pages["gameplay"].analyze_block_reason() == "analysis.need_video"


def test_recording_survives_capture_cut_off_and_loads_as_one_video(win, qtbot):
    """Windows cutting off capture (e.g. Fortnite switching display mode) must not lose the recording."""
    rc = win.recording
    rc.test_part_seconds = 1.5  # each synthetic part ends by itself, like a lost capture session
    assert rc.start()
    qtbot.waitUntil(lambda: rc.recorder.restarts >= 2, timeout=30000)
    assert rc.is_recording and win.sidebar.rec_pill.isVisibleTo(win.sidebar)
    page = win.pages["gameplay"]
    assert "resumed automatically" in page.rec_info.text()
    rc.stop()
    assert page._last_recording and len(page._last_recording) >= 2
    assert "parts" in page.rec_info.text()
    page.rec_load.click()
    qtbot.waitUntil(lambda: page.current is not None and not page.loading, timeout=60000)
    assert "_part" not in page.current.meta.path and page.current.meta.duration_s > 2.5
