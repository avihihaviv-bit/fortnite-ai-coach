"""Phase 8: exercise catalog, personal plan generation, completion tracking. Uses TEST DATA reports."""

import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from fortnite_coach.coaching import taxonomy
from fortnite_coach.coaching.exercises_catalog import BY_ID, CATALOG, WARMUP_ID, templates_for_mistake
from fortnite_coach.coaching.training_plan import generate_plan, target_difficulty
from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import Mistake, Report, TrainingPlan
from fortnite_coach.db.repositories import plan_repo
from tests.helpers import add_test_report

CATEGORIES = {"warm_up", "mechanics", "editing", "building", "piece_control", "aim", "realistic_1v1", "box_fights",
              "zone_wars", "game_sense"}


def test_catalog_complete_and_bilingual():
    assert len({t.id for t in CATALOG}) == len(CATALOG)
    for t in CATALOG:
        assert t.category in CATEGORIES and t.difficulty in ("easy", "medium", "hard") and t.duration_min > 0
        for field in (t.name, t.goal, t.instructions, t.success, t.level_up, t.map_type):
            assert field.en.strip() and field.he.strip()
        for code in t.targets:
            assert code in taxonomy.MISTAKES_BY_CODE, code


def test_every_tracked_mistake_has_an_exercise():
    missing = [m.code for m in taxonomy.MISTAKES if not templates_for_mistake(m.code)]
    assert not missing, missing


def test_no_invented_map_codes():
    blob = str([(t.map_type.en, t.instructions.en, t.map_type.he) for t in CATALOG])
    assert not re.search(r"\b\d{4}-\d{4}-\d{4}\b", blob)


def test_difficulty_follows_score():
    assert target_difficulty(None) == "easy" and target_difficulty(40) == "easy"
    assert target_difficulty(60) == "medium" and target_difficulty(90) == "hard"


def _add_mistakes(db, session_id, codes, ts=30.0):
    with db.session() as s:
        rep = s.query(Report).filter_by(session_id=session_id).one()
        for code in codes:
            m = taxonomy.MISTAKES_BY_CODE[code]
            s.add(Mistake(report_id=rep.id, skill=m.skill.value, code=code, severity="high", timestamp_s=ts,
                          what_happened="TEST DATA", how_to_practice=f"TEST DATA drill for {code}", evidence="TEST DATA"))


def test_no_plan_without_analyzed_sessions(tmp_path):
    db = Database(tmp_path / "c.db").init()
    assert generate_plan(db) is None and plan_repo.active_plan(db) is None


def test_plan_prioritizes_repeated_mistakes(tmp_path):
    db = Database(tmp_path / "c.db").init()
    s1 = add_test_report(db, "f1", {"editing": (45, 2), "aim": (80, 2)})
    _add_mistakes(db, s1, ["EDIT_EXPOSED_AFTER", "GS_LATE_ROTATION"])
    s2 = add_test_report(db, "f2", {"editing": (50, 2)})
    _add_mistakes(db, s2, ["EDIT_EXPOSED_AFTER", "AIM_LOST_TRACKING"], ts=65)
    plan_id = generate_plan(db)
    plan = plan_repo.active_plan(db)
    assert plan.id == plan_id
    ids = [e.template_id for e in plan.exercises]
    assert ids[0] == WARMUP_ID
    assert ids[1] == "edit_reset_drill"  # the repeated mistake comes first, easy drill for a low editing score
    reason = json.loads(plan.exercises[1].reason)
    assert reason["kind"] == "repeated" and reason["sessions"] == 2 and "TEST DATA drill" in reason["note"]
    assert len(plan.exercises) <= 4
    assert "AIM_LOST_TRACKING" in sum((e.source_mistake_codes for e in plan.exercises), [])


def test_regenerate_keeps_history(tmp_path):
    db = Database(tmp_path / "c.db").init()
    add_test_report(db, "f1", {"building": (40, 1)})
    first = generate_plan(db)
    second = generate_plan(db)
    assert first != second and plan_repo.active_plan(db).id == second
    with db.session() as s:
        assert s.query(TrainingPlan).count() == 2 and s.query(TrainingPlan).filter_by(is_active=True).count() == 1


def test_completion_tracking(tmp_path):
    db = Database(tmp_path / "c.db").init()
    add_test_report(db, "f1", {"building": (40, 1)})
    generate_plan(db)
    ex = plan_repo.active_plan(db).exercises[0]
    plan_repo.complete_exercise(db, ex.id, 12, 4)
    plan_repo.complete_exercise(db, ex.id, 8, None)
    t = plan_repo.totals(db, since=datetime.now(timezone.utc) - timedelta(days=7))
    assert (t.completions, t.minutes, t.this_week) == (2, 20, 2)
    plan_repo.undo_last_completion(db, ex.id)
    assert plan_repo.totals(db).completions == 1
    with pytest.raises(ValueError):
        plan_repo.complete_exercise(db, ex.id, 5, 9)


def test_training_effect_is_measured_not_guessed(tmp_path):
    db = Database(tmp_path / "c.db").init()
    s1 = add_test_report(db, "f1", {"editing": (40, 1)})
    _add_mistakes(db, s1, ["EDIT_EXPOSED_AFTER", "EDIT_EXPOSED_AFTER"])
    generate_plan(db)
    ex = [e for e in plan_repo.active_plan(db).exercises if e.template_id == "edit_reset_drill"][0]
    assert plan_repo.training_effects(db) == []  # no completion yet
    plan_repo.complete_exercise(db, ex.id, 10, 3)
    assert plan_repo.training_effects(db) == []  # no session after the training yet
    later = datetime.now(timezone.utc) + timedelta(minutes=5)
    s2 = add_test_report(db, "f2", {"editing": (60, 1)})
    with db.session() as s:
        s.execute(update(Report).where(Report.session_id == s2).values(created_at=later))
    eff = plan_repo.training_effects(db)
    assert len(eff) == 1 and eff[0].before_per_session == 2.0 and eff[0].after_per_session == 0.0
