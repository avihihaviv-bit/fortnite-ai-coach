from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from fortnite_coach.coaching import taxonomy
from fortnite_coach.core.skills import SKILL_PAGES, Skill
from fortnite_coach.db.engine import Database
from fortnite_coach.db.migrations import MIGRATIONS, migrate
from fortnite_coach.db.repositories import knowledge_repo


def test_every_skill_page_has_criteria_and_mistakes():
    for skill in SKILL_PAGES:
        assert len(taxonomy.criteria_for(skill)) >= 5, skill
        assert len(taxonomy.mistakes_for(skill)) >= 3, skill


def test_new_required_topics_present():
    codes = {c.code for cs in taxonomy.CRITERIA.values() for c in cs}
    for required in ("protected_tunneling", "retakes", "tarping", "multi_edits", "classics", "edit_reset",
                     "right_hand_peeks", "flicking", "smg_tracking", "strafing", "rotations",
                     "third_party_awareness", "endgame", "storm_decisions"):
        assert required in codes


def test_codes_unique_and_bilingual():
    crit = [(s, c.code) for s, cs in taxonomy.CRITERIA.items() for c in cs]
    assert len(crit) == len(set(crit))
    codes = [m.code for m in taxonomy.MISTAKES]
    assert len(codes) == len(set(codes))
    for item in [*taxonomy.MISTAKES, *(c for cs in taxonomy.CRITERIA.values() for c in cs)]:
        assert item.en.strip() and item.he.strip()
    for m in taxonomy.MISTAKES:
        assert m.code.isupper() and isinstance(m.skill, Skill)


def test_unmeasurable_inputs_declared():
    joined = " ".join(taxonomy.NOT_MEASURABLE_EN)
    for word in ("DPI", "sensitivity", "reaction time"):
        assert word in joined


def test_builtin_pack_is_season_independent():
    pack = knowledge_repo.load_builtin_pack()
    for e in pack["entries"]:
        assert e["key"] and e["title_he"] and e["content"]
    # no map codes in the fundamentals pack (pattern like 1234-5678-9012)
    import re

    assert not re.search(r"\b\d{4}-\d{4}-\d{4}\b", str(pack))


def test_seed_is_idempotent(tmp_path):
    db = Database(tmp_path / "c.db").init()
    n = knowledge_repo.seed_builtin(db)
    assert n == len(knowledge_repo.load_builtin_pack()["entries"])
    assert knowledge_repo.seed_builtin(db) == 0
    entries = knowledge_repo.current_entries(db)
    assert all(e.kind == "fundamental" and e.source_name for e in entries)


def test_researched_entry_requires_source_and_date(tmp_path):
    db = Database(tmp_path / "c.db").init()
    with pytest.raises(ValueError):
        knowledge_repo.add_researched_entry(db, topic="weapons", title="x", content="y", source_name="",
                                            source_url="", retrieved_at=None, game_version=None)
    eid = knowledge_repo.add_researched_entry(
        db, topic="weapons", title="TEST DATA", content="TEST DATA", source_name="Test source",
        source_url="https://example.com", retrieved_at=datetime.now(timezone.utc), game_version="test")
    assert eid > 0


def test_v1_database_upgrades_to_v2(tmp_path):
    """A database created by the Phase 3 build (schema v1) upgrades in place."""
    db = Database(tmp_path / "old.db")
    with db.engine.begin() as conn:  # build a genuine v1 knowledge table without the new columns
        conn.execute(text("CREATE TABLE schema_version (version INTEGER NOT NULL)"))
        conn.execute(text("INSERT INTO schema_version VALUES (1)"))
        conn.execute(text("CREATE TABLE knowledge (id INTEGER PRIMARY KEY, topic VARCHAR(32), title VARCHAR(200), "
                          "content TEXT, kind VARCHAR(16), game_version VARCHAR(32), source_name VARCHAR(200), "
                          "source_url TEXT, retrieved_at DATETIME, updated_at DATETIME, is_current BOOLEAN)"))
    assert migrate(db.engine, MIGRATIONS[:2]) == 2
    with db.engine.connect() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(knowledge)"))}
    assert {"key", "title_he"} <= cols
