"""Shots / headshots / edits percentages and 1-10 scores. All model output here is TEST DATA."""

import json

from fortnite_coach.ai.gemini_response_parser import clean_stats, load_segment_result, validate_segment


def parse_segment(text, i, a, b):
    return validate_segment(load_segment_result(text), i, a, b)
from fortnite_coach.coaching.aggregate import aggregate
from fortnite_coach.coaching.stats_view import score10, stats_lines
from tests.fake_gemini import segment_json


def tr(key, **kw):  # simple stand-in for the translator
    return key + " " + " ".join(f"{k}={v}" for k, v in sorted(kw.items()))


def seg(stats, start="00:05"):
    d = json.loads(segment_json(start))
    d["stats"] = stats
    return json.dumps(d)


def test_clean_stats_never_invents():
    s = clean_stats({"shots_fired": 20, "shots_hit": 25, "edits_attempted": 4, "edits_completed": 3,
                     "headshots": 2, "fights": -1})
    assert "shots_hit" not in s            # more hits than shots: dropped, not "fixed"
    assert "headshots" not in s            # headshots need their hits
    assert s["edits_completed"] == 3 and "fights" not in s
    assert clean_stats(None) == {}


def test_percentages_and_thresholds():
    s1 = parse_segment(seg({"shots_fired": 30, "shots_hit": 12, "headshots": 3, "edits_attempted": 6,
                            "edits_completed": 5, "fights": 2, "fights_won": 1}), 0, 0, 120)
    s2 = parse_segment(seg({"shots_fired": 20, "shots_hit": 8, "headshots": 1}, "02:10"), 1, 120, 240)
    s3 = parse_segment(seg(None, "04:10"), 2, 240, 360)
    agg = aggregate([s1, s2, s3])
    st = agg.stats
    assert st["shots_fired"] == 50 and st["shots_hit"] == 20 and st["headshots"] == 4
    lines = stats_lines(st, tr)
    assert any("stats.accuracy " in l and "pct=40" in l for l in lines)        # 20 / 50
    assert any("stats.headshots " in l and "pct=20" in l for l in lines)       # 4 / 20 hits
    assert any("stats.edits " in l and "pct=83" in l for l in lines)           # 5 / 6
    assert any("stats.partial" in l and "n=2" in l and "total=3" in l for l in lines)


def test_too_few_to_count_says_so():
    lines = stats_lines({"shots_fired": 3, "shots_hit": 2, "_total": 1}, tr)
    assert any(l.startswith("stats.accuracy_none") for l in lines)
    assert any(l.startswith("stats.edits_none") for l in lines)


def test_score10():
    assert score10(73) == "7.3" and score10(80) == "8" and score10(3) == "1" and score10(None) is None


def test_report_shows_stats_and_scores(qtbot, tmp_path, sample_video):
    from fortnite_coach.app import create_app
    from fortnite_coach.config.paths import AppPaths
    from fortnite_coach.db.engine import Database
    from fortnite_coach.i18n.translator import get_translator
    from fortnite_coach.ui.main_window import MainWindow
    from fortnite_coach.workers.task import wait_all
    from tests.fake_gemini import FakeClient
    from tests.test_ui_analysis import connect, load

    create_app([])
    paths = AppPaths(tmp_path / "h").ensure()
    db = Database(paths.database).init()
    client = FakeClient(responses=[seg({"shots_fired": 10, "shots_hit": 4, "headshots": 1, "edits_attempted": 5,
                                        "edits_completed": 4}, "00:02")])
    w = MainWindow(db, paths, recording_source="test", client_factory=lambda k, t: client)
    qtbot.addWidget(w)
    w.set_language("en")
    connect(w, qtbot)
    page = load(w, qtbot, sample_video)
    page.confirm = lambda *a: True
    page.start_analysis()
    qtbot.waitUntil(lambda: w.current_key == "history", timeout=60000)
    texts = [l.text() for l in w.pages["history"].report_holder.findChildren(type(w.pages["history"].empty.title))]
    joined = "\n".join(texts)
    assert "Shots that hit: <b>40%</b> (4 of 10)" in joined
    assert "Edits that worked: <b>80%</b>" in joined
    assert "Headshots: " in joined and "/10" in joined
    wait_all()
    w._quitting = True
    db.close()
    get_translator().set_language("he")
