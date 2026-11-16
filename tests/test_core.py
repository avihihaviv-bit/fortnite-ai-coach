from fortnite_coach.config.paths import AppPaths, default_data_dir, resource_path
from fortnite_coach.config.settings import AppSettings, Language
from fortnite_coach.core.game_modes import GameMode, SUPPORTED_VIDEO_EXTENSIONS
from fortnite_coach.core.skills import ALL_SKILLS, SKILL_PAGES, Skill


def test_ten_skills():
    assert len(ALL_SKILLS) == 10
    assert set(SKILL_PAGES) <= set(ALL_SKILLS)


def test_seven_game_modes_and_training_flag():
    assert len(GameMode) == 7
    assert GameMode.BOX_FIGHTS.is_training
    assert not GameMode.BATTLE_ROYALE.is_training


def test_supported_extensions():
    assert SUPPORTED_VIDEO_EXTENSIONS == {".mp4", ".mov", ".mkv", ".webm"}


def test_data_dir_override(isolated_home):
    assert default_data_dir() == isolated_home
    paths = AppPaths.default().ensure()
    assert paths.database.parent == isolated_home
    assert paths.frames_dir.is_dir() and paths.clips_dir.is_dir()


def test_resource_path_finds_catalog():
    assert resource_path("i18n/en.json").is_file()


def test_settings_defaults_have_no_secret():
    s = AppSettings()
    assert s.language is Language.HEBREW
    dumped = s.model_dump_json().lower()
    assert "api_key" not in dumped and "apikey" not in dumped
    assert s.gemini.paid_usage_acknowledged is False
