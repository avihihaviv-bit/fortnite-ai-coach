from fortnite_coach.coaching.levels import (
    MIN_CONFIDENCE, level_from_xp, level_ups, xp_for_play, xp_to_next,
)


def test_xp_by_difficulty_and_confidence():
    assert xp_for_play("hard", 1.0, "hit marker") == 50
    assert xp_for_play("medium", 1.0, "x") == 25
    assert xp_for_play("easy", 0.8, "x") == 8
    assert xp_for_play("hard", 0.7, "x") == 35


def test_no_xp_without_evidence_or_confidence():
    assert xp_for_play("hard", MIN_CONFIDENCE - 0.01, "x") == 0
    assert xp_for_play("hard", None, "x") == 0
    assert xp_for_play("hard", 1.0, "   ") == 0
    assert xp_for_play("legendary", 1.0, "x") == 0


def test_level_curve():
    assert xp_to_next(1) == 100 and xp_to_next(2) == 150
    assert level_from_xp(0).level == 1 and level_from_xp(0).tier == "bronze"
    assert level_from_xp(99).level == 1
    lv = level_from_xp(100)
    assert lv.level == 2 and lv.xp_into_level == 0 and lv.xp_for_next == 150
    assert level_from_xp(250).level == 3
    assert level_from_xp(10_000).tier in ("gold", "platinum", "diamond")
    assert level_ups(90, 260) == 2
