from sqlalchemy import func, inspect, select, text

from fortnite_coach.config.paths import AppPaths
from fortnite_coach.config.settings import AppSettings, Language
from fortnite_coach.db.engine import Database
from fortnite_coach.db.migrations import LATEST_VERSION, migrate
from fortnite_coach.db.models import Mistake, Report, Setting, SkillScore
from fortnite_coach.db.repositories import data_repo, profile_repo, session_repo, settings_repo, stats_repo
from tests.helpers import add_test_report

EXPECTED_TABLES = {
    "player_profile", "videos", "sessions", "reports", "skill_scores", "mistakes", "training_plans",
    "exercises", "exercise_completions", "api_usage", "settings", "knowledge", "schema_version",
}


def make_db(tmp_path):
    return Database(tmp_path / "coach.db").init()


def test_init_creates_all_tables(tmp_path):
    db = make_db(tmp_path)
    assert EXPECTED_TABLES <= set(inspect(db.engine).get_table_names())


def test_migrations_idempotent_and_incremental(tmp_path):
    db = make_db(tmp_path)
    assert migrate(db.engine) == LATEST_VERSION  # re-run is a no-op
    applied = []

    def v_next(conn):
        applied.append(True)
        conn.execute(text("CREATE TABLE extra_test (id INTEGER)"))

    from fortnite_coach.db.migrations import MIGRATIONS

    assert migrate(db.engine, [*MIGRATIONS, (LATEST_VERSION + 1, v_next)]) == LATEST_VERSION + 1
    assert migrate(db.engine, [*MIGRATIONS, (LATEST_VERSION + 1, v_next)]) == LATEST_VERSION + 1
    assert applied == [True]


def test_settings_round_trip_and_persist_across_reopen(tmp_path):
    db = make_db(tmp_path)
    assert settings_repo.load_settings(db) == AppSettings()
    s = AppSettings(language=Language.ENGLISH)
    s.limits.max_requests_per_day = 5
    settings_repo.save_settings(db, s)
    db.close()
    db2 = make_db(tmp_path)
    loaded = settings_repo.load_settings(db2)
    assert loaded.language is Language.ENGLISH and loaded.limits.max_requests_per_day == 5


def test_invalid_stored_settings_fall_back_to_defaults(tmp_path):
    db = make_db(tmp_path)
    with db.session() as s:
        s.add(Setting(key=settings_repo.KEY, value={"language": "klingon"}))
    assert settings_repo.load_settings(db) == AppSettings()


def test_profile_single_row(tmp_path):
    db = make_db(tmp_path)
    a = profile_repo.get_or_create_profile(db)
    b = profile_repo.get_or_create_profile(db)
    assert a.id == b.id and a.input_device == "keyboard_mouse"
    assert profile_repo.update_profile(db, display_name="  Player1  ").display_name == "Player1"


def test_same_video_not_duplicated(tmp_path):
    db = make_db(tmp_path)
    info = session_repo.VideoInfo(path="C:/a.mp4", fingerprint="abc", size_bytes=10)
    first = session_repo.upsert_video(db, info)
    moved = session_repo.VideoInfo(path="D:/moved.mp4", fingerprint="abc", size_bytes=10)
    assert session_repo.upsert_video(db, moved) == first
    assert session_repo.counts(db)["videos"] == 1


def test_delete_session_cascades(tmp_path):
    db = make_db(tmp_path)
    sid = add_test_report(db, "f1", {"aim": (60, 2)})
    with db.session() as s:
        rep = s.scalars(select(Report)).one()
        s.add(Mistake(report_id=rep.id, skill="aim", code="AIM_TEST", severity="low", what_happened="TEST DATA"))
    assert session_repo.delete_session(db, sid)
    with db.session() as s:
        assert s.scalar(select(func.count(Report.id))) == 0
        assert s.scalar(select(func.count(SkillScore.id))) == 0
        assert s.scalar(select(func.count(Mistake.id))) == 0


def test_stats_empty_means_not_enough_data(tmp_path):
    st = stats_repo.dashboard_stats(make_db(tmp_path))
    assert st.analyzed_sessions == 0 and st.skills == {}
    assert st.overall is None and st.strongest is None and st.weakest is None


def test_stats_use_only_evidence_backed_scores(tmp_path):
    db = make_db(tmp_path)
    add_test_report(db, "f1", {"aim": (60, 3), "building": (40, 2), "editing": (None, 0), "movement": (90, 0)})
    add_test_report(db, "f2", {"aim": (80, 1)})
    st = stats_repo.dashboard_stats(db)
    assert st.analyzed_sessions == 2
    assert set(st.skills) == {"aim", "building"}  # null and zero-evidence scores ignored
    assert st.skills["aim"].average == 70.0 and st.skills["aim"].samples == 2
    assert st.overall is None  # fewer than 3 rated skills
    assert st.strongest == "aim" and st.weakest == "building"


def test_overall_needs_three_skills(tmp_path):
    db = make_db(tmp_path)
    add_test_report(db, "f1", {"aim": (60, 1), "building": (40, 1), "editing": (50, 1)})
    assert stats_repo.dashboard_stats(db).overall == 50.0


def test_delete_all_keeps_settings_and_profile(tmp_path):
    db = make_db(tmp_path)
    settings_repo.save_settings(db, AppSettings(language=Language.ENGLISH))
    profile_repo.get_or_create_profile(db)
    add_test_report(db, "f1", {"aim": (60, 1)})
    data_repo.delete_all_analysis_data(db)
    assert session_repo.counts(db) == {"videos": 0, "sessions": 0, "reports": 0}
    assert settings_repo.load_settings(db).language is Language.ENGLISH


def test_clear_cache(tmp_path):
    paths = AppPaths(tmp_path / "home").ensure()
    (paths.frames_dir / "x.jpg").write_bytes(b"0" * 2048)
    assert data_repo.clear_cache(paths.cache_dir) == 2048
    assert not any(paths.cache_dir.iterdir())
