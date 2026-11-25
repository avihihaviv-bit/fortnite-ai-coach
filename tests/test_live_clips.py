"""Live Coach, start modes, hotkey box, clip library and batch analysis. All model replies are TEST DATA."""

import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from fortnite_coach.ai import usage_tracker
from fortnite_coach.app import create_app
from fortnite_coach.coaching import taxonomy
from fortnite_coach.coaching.exercises_catalog import templates_for_mistake
from fortnite_coach.coaching.resources import QUERIES
from fortnite_coach.config.paths import AppPaths
from fortnite_coach.core.skills import Skill
from fortnite_coach.db.engine import Database
from fortnite_coach.i18n.translator import get_translator
from fortnite_coach.library import clips as clip_lib
from fortnite_coach.live.coach import clean_tip
from fortnite_coach.workers.task import wait_all
from tests.fake_gemini import FakeAPIError, FakeClient, segment_json
from tests.test_ui_analysis import connect

TIP = "TEST DATA: wall your left side before healing"


@pytest.fixture
def win(qtbot, tmp_path):
    from fortnite_coach.ui.main_window import MainWindow

    create_app([])
    paths = AppPaths(tmp_path / "home").ensure()
    db = Database(paths.database).init()
    client = FakeClient(responses=[TIP])
    w = MainWindow(db, paths, recording_source="test", client_factory=lambda k, t: client)
    w.set_language("en")
    qtbot.addWidget(w)
    w.show()
    yield w, client, qtbot
    w.live.stop()
    if w.recording.is_recording:
        w.recording.stop()
    wait_all()
    w._quitting = True
    db.close()
    get_translator().set_language("he")


# ---------------------------------------------------------------- units
def test_clean_tip():
    assert clean_tip("NONE") is None
    assert clean_tip("  none.  ") is None
    assert clean_tip("") is None
    assert clean_tip('"Take high ground now"') == "Take high ground now"
    assert len(clean_tip("x " * 200)) <= 160


def test_hotkey_box_records_combination(qtbot):
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent

    from fortnite_coach.recording.hotkeys import parse_hotkey
    from fortnite_coach.ui.widgets.hotkey_edit import HotkeyEdit, combo_text

    create_app([])
    assert combo_text(Qt.Key.Key_F9, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier) == "Ctrl+Shift+F9"
    assert combo_text(Qt.Key.Key_F2, Qt.KeyboardModifier.NoModifier) == "F2"  # a function key alone is allowed
    assert combo_text(Qt.Key.Key_R, Qt.KeyboardModifier.NoModifier) is None  # never a plain letter (game key)
    assert combo_text(Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier) is None
    box = HotkeyEdit()
    qtbot.addWidget(box)
    box.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_K, Qt.KeyboardModifier.AltModifier))
    assert box.text() == "Alt+K"
    parse_hotkey(box.text())


def test_mechanics_category_complete():
    assert len(taxonomy.criteria_for(Skill.MECHANICS)) >= 8
    mech = taxonomy.mistakes_for(Skill.MECHANICS)
    assert {"MECH_NO_PRE_FIRE", "MECH_SLOW_SWAP"} <= {m.code for m in mech}
    assert taxonomy.good_plays_for(Skill.MECHANICS)
    for m in mech:
        assert m.code in QUERIES, m.code
        assert templates_for_mistake(m.code), m.code  # every mechanics mistake has a drill


def test_clip_scan(tmp_path):
    medal = tmp_path / "Videos" / "Medal" / "Clips" / "Fortnite"
    medal.mkdir(parents=True)
    (medal / "clip1.mp4").write_bytes(b"\0" * 60_000)
    (medal / "tiny.mp4").write_bytes(b"\0" * 100)       # too small to be a clip
    (medal / "notes.txt").write_bytes(b"\0" * 60_000)    # not a video
    other = tmp_path / "mine"
    other.mkdir()
    (other / "match.MKV").write_bytes(b"\0" * 70_000)
    detected = clip_lib.detected_folders(tmp_path)
    assert ("clips.src_medal", tmp_path / "Videos" / "Medal") in detected
    found = clip_lib.scan([p for _, p in detected] + [other])
    assert sorted(c.name for c in found) == ["clip1.mp4", "match.MKV"]  # Videos + Medal overlap: no duplicates


# ---------------------------------------------------------------- live coach
def _enable_live(w):
    s = w.settings
    s.live.acknowledged = True
    w._save_settings(s)


def test_live_needs_ack_and_key(win):
    w, client, qtbot = win
    assert w.live.block_reason() == "live.need_ack"
    assert not w.live.start()
    _enable_live(w)
    assert w.live.block_reason() == "live.need_gemini"
    connect(w, qtbot)
    assert w.live.block_reason() is None


def test_live_tip_shows_in_overlay(win):
    w, client, qtbot = win
    connect(w, qtbot)
    _enable_live(w)
    page = w.pages["gameplay"]
    page.start_mode.setCurrentIndex(page.start_mode.findData("live"))
    assert w.settings.recording.start_mode == "live"
    assert page.rec_start.text() == "Start Live Coach"
    assert page.rec_start.isEnabled()
    page.rec_start.click()
    assert w.live.active and not w.recording.is_recording
    assert "LIVE" in w.windowTitle()
    folder = w.live.capture.folder
    qtbot.waitUntil(lambda: len(w.live.capture.latest(5)) >= 2, timeout=20000)
    w.live.request_now()
    qtbot.waitUntil(lambda: w.live.tips_shown == 1, timeout=10000)
    assert TIP in w.overlay.text and w.overlay.isVisible()
    assert usage_tracker.live_requests_today(w.db) == 1
    model, contents, _cfg = client.generate_calls[-1]
    assert len(contents[0].parts) >= 3  # screenshots + text prompt
    page.rec_stop.click()
    assert not w.live.active
    assert not folder.exists()  # screenshots are deleted


def test_live_stops_on_fatal_error(win):
    w, client, qtbot = win
    connect(w, qtbot)
    _enable_live(w)
    w.settings.live.model = w.settings.gemini.model  # same model: nothing to fall back to
    client._responses = [FakeAPIError(429, "RESOURCE_EXHAUSTED quota limit: 0 TEST DATA")]
    assert w.live.start()
    qtbot.waitUntil(lambda: len(w.live.capture.latest(5)) >= 2, timeout=20000)
    w.live.request_now()
    qtbot.waitUntil(lambda: not w.live.active, timeout=10000)
    assert w.live.last_error == "gemini.err_no_free_quota"
    assert "Live Coach stopped" in w.overlay.text


def test_live_daily_limit(win):
    w, client, qtbot = win
    connect(w, qtbot)
    _enable_live(w)
    w.settings.live.max_tips_per_day = 1
    usage_tracker.record(w.db, model="m", kind="live", success=True)
    assert w.live.block_reason() == "live.err_daily_limit"
    assert not w.live.start()


def test_record_plus_live_mode_starts_and_stops_both(win):
    w, client, qtbot = win
    connect(w, qtbot)
    _enable_live(w)
    w.settings.recording.start_mode = "record_live"
    w.start_session()
    assert w.recording.is_recording and w.live.active
    w.stop_session()
    assert not w.recording.is_recording and not w.live.active
    qtbot.waitUntil(lambda: w.pages["gameplay"]._last_recording is not None, timeout=10000)


def test_live_settings_card(win):
    w, client, qtbot = win
    card = w.settings_page.live_card
    card.ack.setChecked(True)
    card.interval.setValue(20)
    card.hotkey.setText(w.settings.recording.hotkey_start)  # clashes with recording
    card.save()
    assert "Invalid" in card.feedback.text() and w.settings.live.interval_s != 20  # bad hotkey: nothing else saved
    assert w.settings.live.acknowledged  # the tick itself is saved at once
    card.hotkey.setText("Ctrl+Shift+F12")
    card.save()
    assert w.settings.live.acknowledged and w.settings.live.interval_s == 20
    assert w.settings.live.hotkey == "Ctrl+Shift+F12"
    card.preview_btn.click()
    assert w.overlay.isVisible() and "preview" in w.overlay.text


# ---------------------------------------------------------------- clip library
def test_clip_library_open_and_batch(win, sample_video, tmp_path):
    w, client, qtbot = win
    client._responses = [segment_json("00:02"), segment_json("00:03", mistake=False)]
    folder = tmp_path / "medal_clips"
    folder.mkdir()
    a = folder / "clip_a.mp4"
    b = folder / "clip_b.mp4"
    shutil.copy(sample_video, a)
    shutil.copy(sample_video, b)
    with open(b, "ab") as f:  # different fingerprint than clip_a
        f.write(b"\0" * 64)
    page = w.pages["clips"]
    page.home = tmp_path / "nohome"
    page.add_folder(str(folder))
    assert str(folder) in w.settings.clip_folders
    qtbot.waitUntil(lambda: page.clip_list.count() == 2, timeout=10000)
    assert page.batch_block_reason() == "clips.need_selection"
    page.set_checked([str(a), str(b)])
    assert page.batch_block_reason() == "analysis.need_key"
    connect(w, qtbot)
    assert page.batch_block_reason() is None
    asked = []
    page.confirm = lambda title, text: asked.append(text) or True
    page.start_batch()
    qtbot.waitUntil(lambda: page.results_list.count() == 2, timeout=60000)
    assert "Requests to send: 2" in asked[0]
    assert "2 of 2" in page.message
    assert all(r.report_id for r in page.results)
    qtbot.waitUntil(lambda: "analyzed" in page.clip_list.item(0).text(), timeout=10000)
    # open one clip in the analysis page
    page.open_clip(str(a))
    assert w.current_key == "gameplay"
    qtbot.waitUntil(lambda: w.pages["gameplay"].current is not None, timeout=20000)
    assert Path(w.pages["gameplay"].current.meta.path).name == "clip_a.mp4"


def test_record_card_renders_with_windows_hotkeys(win, monkeypatch):
    """The hotkey lines only render on Windows; render them here too."""
    from fortnite_coach.ui.pages import analysis_page

    w, client, qtbot = win
    monkeypatch.setattr(analysis_page, "hotkeys_supported", lambda: True)
    page = w.pages["gameplay"]
    page.start_mode.setCurrentIndex(page.start_mode.findData("record_live"))
    page._render_recording()
    assert "F3" in page.rec_info.text() and "F2" in page.rec_info.text()
    assert "alternate build keys" in page.rec_info.text()  # honest warning about F1-F4


# ---------------------------------------------------------------- what to search
def test_clean_query():
    from fortnite_coach.ai.gemini_response_parser import clean_query

    assert clean_query("how to pre fire <script>") == "fortnite how to pre fire script"
    assert clean_query("Fortnite tarping tutorial") == "Fortnite tarping tutorial"
    assert clean_query("x") == ""
    assert len(clean_query("fortnite " + "word " * 50)) <= 90


def test_links_use_ai_phrase_for_all_three_sites():
    from fortnite_coach.coaching.resources import links_html

    html = links_html("EDIT_SLOW", "editing", "Search:", "fortnite double edit pre fire box fight")
    assert "fortnite double edit pre fire box fight" in html
    for host in ("youtube.com/results", "tiktok.com/search", "google.com/search"):
        assert host in html
    assert "fortnite+double+edit+pre+fire+box+fight" in html
    fallback = links_html("EDIT_SLOW", "editing", "Search:", "")
    assert QUERIES["EDIT_SLOW"] in fallback  # curated phrase when the AI gave none


def test_struggles_ranked_and_shown_on_dashboard(win, sample_video):
    from fortnite_coach.db.repositories import report_repo
    from tests.test_ui_analysis import load

    w, client, qtbot = win
    client._responses = [segment_json("00:02")]
    connect(w, qtbot)
    page = load(w, qtbot, sample_video)
    page.confirm = lambda *a: True
    page.start_analysis()
    qtbot.waitUntil(lambda: page.job is not None and not page.job.running, timeout=60000)
    st = report_repo.struggles(w.db)
    assert st and st[0].code == "EDIT_EXPOSED_AFTER"
    assert st[0].query == "fortnite how to reset edits in box fights TEST DATA"
    dash = w.pages["dashboard"]
    assert dash.search_list.isVisible() or not dash.isVisible()
    text = dash.search_list.text()
    assert "tiktok.com/search?q=fortnite+how+to+reset+edits" in text
    assert "TEST DATA: stayed in the open edit" in text  # the player's own moment
    assert report_repo.latest_search_queries(w.db)["EDIT_EXPOSED_AFTER"].startswith("fortnite how to reset")


def test_live_stops_when_turned_off_in_settings(win):
    w, client, qtbot = win
    connect(w, qtbot)
    _enable_live(w)
    assert w.live.start()
    w.settings.live.acknowledged = False
    w.live.request_now()
    assert not w.live.active and w.live.last_error == "live.need_ack"


def test_capture_falls_back_to_gdi_after_fast_failures(tmp_path):
    from fortnite_coach.live.capture import FrameCapture

    cap = FrameCapture("ffmpeg-does-not-matter", tmp_path / "f")

    class Dead:
        def poll(self):
            return 1

    starts = []
    cap.start = lambda: (starts.append(cap.source), setattr(cap, "_started", __import__("time").monotonic()))
    for _ in range(3):
        cap._proc = Dead()
        cap._started = __import__("time").monotonic()
        cap.ensure_running()
    assert cap.source == "gdigrab" and starts[-1] == "gdigrab"


def test_videos_root_scanned_shallow(tmp_path):
    videos = tmp_path / "Videos"
    deep = videos / "Movies" / "x"
    deep.mkdir(parents=True)
    (videos / "top.mp4").write_bytes(b"\0" * 60_000)
    (deep / "movie.mp4").write_bytes(b"\0" * 60_000)
    found = clip_lib.scan([videos], shallow={str(videos)})
    assert [c.name for c in found] == ["top.mp4"]


def test_live_skips_static_screens_and_avoids_repeats():
    from fortnite_coach.live.coach import AVOID, looks_static

    assert looks_static([b"x" * 50_000, b"y" * 50_010, b"z" * 50_005])   # menu / pause: nothing changed
    assert not looks_static([b"x" * 50_000, b"y" * 58_000])              # gameplay: frames differ
    assert "repeat" in AVOID["en"]


def test_live_tip_falls_back_to_plain_settings():
    from fortnite_coach.ai.gemini_service import GeminiService

    client = FakeClient(responses=[FakeAPIError(400, "thinking_level is not supported TEST DATA"), "TEST DATA tip"])
    svc = GeminiService(lambda: "k", "gemini-3-flash", client_factory=lambda k, t: client)
    res = svc.live_tip([b"\xff\xd8jpg"], "sys", "prompt")
    assert res.text == "TEST DATA tip" and svc._live_minimal
    assert client.generate_calls[-1][2].thinking_config is None


def test_live_warns_after_repeated_failures(win):
    w, client, qtbot = win
    connect(w, qtbot)
    _enable_live(w)
    client._responses = [FakeAPIError(503, "UNAVAILABLE TEST DATA")] * 3
    assert w.live.start()
    seen = []
    w.live.warning.connect(seen.append)
    for _ in range(3):
        w.live._failed(FakeAPIError(503, "UNAVAILABLE TEST DATA"), "m")
    assert seen == ["gemini.err_server"] and w.live.active
    assert "not answering" in w.overlay.text


def test_live_model_auto_prefers_lite_and_falls_back(win):
    from fortnite_coach.ai.gemini_config import live_model

    assert live_model(["gemini-2.5-flash", "gemini-2.5-flash-lite"], "gemini-2.5-flash") == "gemini-2.5-flash-lite"
    assert live_model(["gemini-2.5-flash"], "gemini-2.5-flash") == "gemini-2.5-flash"
    assert live_model(["gemini-2.5-flash-lite"], "gemini-2.5-flash", "gemini-2.5-flash") == "gemini-2.5-flash"
    w, client, qtbot = win
    connect(w, qtbot)  # fake key lists flash + flash-lite
    _enable_live(w)
    assert w.live.start()
    assert w.live.model == "gemini-2.5-flash-lite"
    assert "separately" in w.settings_page.live_card.feedback.text() or "per model" in w.settings_page.live_card.feedback.text()
    w.live._failed(FakeAPIError(429, "RESOURCE_EXHAUSTED limit: 0 TEST DATA"), w.live.model)
    assert w.live.active and w.live.model == w.settings.gemini.model  # switched instead of stopping


def test_f2_toggles_recording_and_loads_the_video(win):
    w, client, qtbot = win
    assert w.settings.recording.hotkey_toggle == "F2" and w.settings.live.hotkey == "F3"
    w.toggle_recording()
    assert w.recording.is_recording and "Recording started" in w.overlay.text
    qtbot.wait(2500)
    w.toggle_recording()
    assert not w.recording.is_recording
    page = w.pages["gameplay"]
    qtbot.waitUntil(lambda: page.current is not None, timeout=30000)  # loaded automatically, ready to analyze
    assert "loading it for analysis" in w.overlay.text or page.current is not None


def test_f3_toggles_live(win):
    w, client, qtbot = win
    connect(w, qtbot)
    _enable_live(w)
    w.toggle_live()
    assert w.live.active and "Live Coach on" in w.overlay.text
    w.toggle_live()
    assert not w.live.active and "Live Coach off" in w.overlay.text


def test_old_settings_upgrade_live_key_and_keep_valid_parts(tmp_path):
    from fortnite_coach.db.models import Setting
    from fortnite_coach.db.repositories import settings_repo

    db = Database(tmp_path / "s.db").init()
    with db.session() as s:
        s.add(Setting(key=settings_repo.KEY, value={
            "language": "en", "live": {"hotkey": "Ctrl+Shift+F11", "acknowledged": True},
            "recording": {"fps": 9999}}))  # an invalid section must not reset everything
    st = settings_repo.load_settings(db)
    assert st.live.hotkey == "F3" and st.live.acknowledged and st.language.value == "en"
    assert st.recording.fps == 60  # invalid section replaced by defaults only
    db.close()


def test_recording_settings_reject_duplicate_hotkeys(win):
    w, client, qtbot = win
    sp = w.settings_page
    sp.hk_toggle.setText("F3")  # same as Live
    sp._save_recording()
    assert w.settings.recording.hotkey_toggle == "F2"
    sp.hk_toggle.setText("F6")
    sp._save_recording()
    assert w.settings.recording.hotkey_toggle == "F6"


def test_f2_with_auto_analyze_produces_a_report(win):
    from fortnite_coach.db.repositories import report_repo

    w, client, qtbot = win
    client._responses = [segment_json("00:01")]
    connect(w, qtbot)
    w.settings.recording.auto_analyze = True
    w.toggle_recording()
    qtbot.wait(3000)
    w.toggle_recording()
    assert "analyzing it now" in w.overlay.text
    qtbot.waitUntil(lambda: bool(report_repo.list_reports(w.db)), timeout=60000)  # no dialog was needed
    qtbot.waitUntil(lambda: w.current_key == "history", timeout=10000)  # the report opens by itself


def test_auto_analyze_without_key_only_loads(win):
    w, client, qtbot = win
    w.settings.recording.auto_analyze = True
    blocked = []
    w.pages["gameplay"].auto_analyze_blocked.connect(blocked.append)
    w.toggle_recording()
    qtbot.wait(2500)
    w.toggle_recording()
    qtbot.waitUntil(lambda: bool(blocked), timeout=30000)
    assert blocked == ["analysis.need_key"] and w.pages["gameplay"].current is not None


def test_focus_reminder_after_start(win, sample_video):
    from fortnite_coach.db.models import Mistake, Report
    from tests.helpers import add_test_report

    w, client, qtbot = win
    assert w.focus_text() is None  # no reports yet: nothing invented
    add_test_report(w.db, "fpf", {"editing": (50, 2)})
    with w.db.session() as s:
        r = s.query(Report).first()
        s.add(Mistake(report_id=r.id, skill="mechanics", code="MECH_NO_PRE_FIRE", severity="high", timestamp_s=3,
                      what_happened="TEST DATA"))
    assert "Today's focus" in w.focus_text()
    w.toggle_recording()
    assert w.overlay.text == "● Recording started"  # confirmations have no coach icon
    qtbot.waitUntil(lambda: "Today's focus" in w.overlay.text, timeout=6000)
    w.toggle_recording()


def test_update_downloads_are_cleaned(tmp_path):
    from fortnite_coach import updater

    (tmp_path / "old-Setup.exe").write_bytes(b"x" * 1000)
    assert updater.cleanup(tmp_path) == 1000 and not list(tmp_path.iterdir())


def test_ticking_live_box_enables_start_without_save(win):
    """User report: ticked the Live box and Start stayed disabled (the tick was only saved by a Save click)."""
    w, client, qtbot = win
    connect(w, qtbot)
    page = w.pages["gameplay"]
    page.start_mode.setCurrentIndex(page.start_mode.findData("live"))
    assert not page.rec_start.isEnabled() and page.rec_fix.isVisibleTo(page)
    page.rec_fix.click()
    assert w.current_key == "settings"
    w.settings_page.live_card.ack.setChecked(True)          # just the tick, no Save
    assert w.settings.live.acknowledged
    assert page.rec_start.isEnabled() and not page.rec_fix.isVisibleTo(page)  # re-checked at once
    assert "Live Coach is on" in w.settings_page.live_card.feedback.text()


def test_fix_button_points_to_key_when_not_connected(win):
    w, client, qtbot = win
    _enable_live(w)
    page = w.pages["gameplay"]
    page.start_mode.setCurrentIndex(page.start_mode.findData("live"))
    assert "Gemini" in page.rec_info.text() and page.rec_fix.isVisibleTo(page)
