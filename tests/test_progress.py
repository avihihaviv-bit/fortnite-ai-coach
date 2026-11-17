"""Phase 9: progress over time, weekly/monthly, repeated vs resolved mistakes, records, comparison. TEST DATA."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import ExerciseCompletion, Mistake, Report, XpEvent
from fortnite_coach.db.repositories import progress_repo
from fortnite_coach.coaching.training_plan import generate_plan
from fortnite_coach.db.repositories import plan_repo
from fortnite_coach.core.game_modes import GameMode
from tests.helpers import add_test_report

BASE = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)  # a Monday


def add(db, fp, scores, days, codes=(), mode=GameMode.BOX_FIGHTS, xp=0, minutes=4.0):
    sid = add_test_report(db, fp, scores, mode=mode)
    with db.session() as s:
        rep = s.query(Report).filter_by(session_id=sid).one()
        rep.created_at = BASE + timedelta(days=days)
        rep.coverage = [{"index": 0, "start_s": 0, "end_s": minutes * 60, "analyzed": True, "note": ""}]
        for code in codes:
            s.add(Mistake(report_id=rep.id, skill="editing", code=code, severity="high", timestamp_s=10,
                          what_happened="TEST DATA", evidence="TEST DATA"))
        if xp:
            s.add(XpEvent(report_id=rep.id, skill="editing", code="EDIT_HARD_FAST", difficulty="hard", amount=xp,
                          timestamp_s=5, evidence="TEST DATA"))
        return rep.id


def test_empty_database_has_no_progress(tmp_path):
    db = Database(tmp_path / "c.db").init()
    assert progress_repo.timeline(db) == [] and progress_repo.periods(db) == []
    assert progress_repo.personal_records(db) == [] and progress_repo.default_pair(db) is None


def test_timeline_scores_only_with_evidence_and_overall_needs_three(tmp_path):
    db = Database(tmp_path / "c.db").init()
    add(db, "a", {"editing": (40, 2), "aim": (None, 0), "building": (70, 0)}, 0)
    add(db, "b", {"editing": (60, 1), "aim": (50, 1), "building": (70, 1)}, 1)
    t = progress_repo.timeline(db)
    assert t[0].scores == {"editing": 40} and t[0].overall is None
    assert t[1].overall == 60.0


def test_weekly_and_monthly_buckets(tmp_path):
    db = Database(tmp_path / "c.db").init()
    add(db, "a", {"editing": (40, 1)}, 0, codes=["EDIT_SLOW"] * 2, xp=50)
    add(db, "b", {"editing": (50, 1)}, 1, codes=["EDIT_SLOW"])
    add(db, "c", {"editing": (55, 1)}, 8)
    weeks = progress_repo.periods(db)
    assert [w.key for w in weeks] == ["2026-W45", "2026-W46"]
    assert (weeks[0].sessions, weeks[0].mistakes, weeks[0].xp, weeks[0].analyzed_min) == (2, 3, 50, 8.0)
    assert weeks[0].mistakes_per_min == 0.38
    months = progress_repo.periods(db, monthly=True)
    assert len(months) == 1 and months[0].sessions == 3


def test_training_counts_in_periods(tmp_path):
    db = Database(tmp_path / "c.db").init()
    add(db, "a", {"editing": (40, 1)}, 0)
    generate_plan(db)
    ex = plan_repo.active_plan(db).exercises[0]
    plan_repo.complete_exercise(db, ex.id, 15, 4)
    with db.session() as s:
        s.execute(update(ExerciseCompletion).values(completed_at=BASE + timedelta(days=1)))
    w = progress_repo.periods(db)[0]
    assert (w.completions, w.training_min) == (1, 15)


def test_repeated_active_and_resolved(tmp_path):
    db = Database(tmp_path / "c.db").init()
    add(db, "a", {"editing": (40, 1)}, 0, codes=["EDIT_SLOW", "EDIT_FAILED"])
    add(db, "b", {"editing": (45, 1)}, 1, codes=["EDIT_SLOW"])
    for i, fp in enumerate(("c", "d", "e")):  # 3 later box-fight sessions without EDIT_FAILED / EDIT_SLOW
        add(db, fp, {"editing": (50, 1)}, 2 + i)
    add(db, "f", {"editing": (50, 1)}, 6, codes=["EDIT_REPEATED"], mode=GameMode.ZONE_WARS)
    st = {m.code: m for m in progress_repo.mistake_statuses(db)}
    assert st["EDIT_FAILED"].status == "resolved"
    assert st["EDIT_SLOW"].status == "resolved" and st["EDIT_SLOW"].sessions == 2
    assert st["EDIT_REPEATED"].status == "active"
    # different game mode sessions do not count toward "resolved"
    add(db, "g", {"editing": (50, 1)}, 7, codes=["EDIT_CROSSHAIR_OFF"], mode=GameMode.ZONE_WARS)
    add(db, "h", {"editing": (50, 1)}, 8, codes=["EDIT_CROSSHAIR_OFF"], mode=GameMode.ZONE_WARS)
    for i, fp in enumerate(("i", "j", "k")):
        add(db, fp, {"editing": (50, 1)}, 9 + i)  # box fights, not comparable
    st = {m.code: m for m in progress_repo.mistake_statuses(db)}
    assert st["EDIT_CROSSHAIR_OFF"].status == "repeated"


def test_personal_records(tmp_path):
    db = Database(tmp_path / "c.db").init()
    add(db, "a", {"editing": (40, 1)}, 0, codes=["EDIT_SLOW"] * 4, xp=25)
    add(db, "b", {"editing": (72, 1)}, 3, codes=["EDIT_SLOW"], xp=60)
    recs = {r.key + r.detail: r for r in progress_repo.personal_records(db)}
    assert recs["best_scoreediting"].value == "72"
    assert recs["most_xp"].value == "60"
    assert recs["fewest_mistakes"].value == "0.25"
    assert recs["hard_plays"].value == "2"


def test_compare_latest_with_previous_same_mode(tmp_path):
    db = Database(tmp_path / "c.db").init()
    a = add(db, "a", {"editing": (40, 1), "aim": (60, 1)}, 0, codes=["EDIT_SLOW", "EDIT_FAILED"])
    add(db, "z", {"editing": (90, 1)}, 1, mode=GameMode.ZONE_WARS)
    b = add(db, "b", {"editing": (55, 1)}, 2, codes=["EDIT_SLOW", "EDIT_REPEATED"], mode=GameMode.BOX_FIGHTS)
    assert progress_repo.default_pair(db) == (a, b)
    c = progress_repo.compare(db, b, a)  # order does not matter
    assert c.older.report_id == a and c.score_changes == [("editing", 40, 55)]
    assert c.gone == ["EDIT_FAILED"] and c.still == ["EDIT_SLOW"] and c.new == ["EDIT_REPEATED"]
