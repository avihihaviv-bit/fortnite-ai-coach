"""UI tests: startup, navigation, RTL/LTR switching, honest empty states."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from fortnite_coach.ai.status import GeminiStatus
from fortnite_coach.app import create_app
from fortnite_coach.i18n.translator import get_translator
from fortnite_coach.ui import icons
from fortnite_coach.ui.sidebar import NAV_KEYS


@pytest.fixture
def env(tmp_path):
    from fortnite_coach.config.paths import AppPaths
    from fortnite_coach.db.engine import Database

    paths = AppPaths(tmp_path / "home").ensure()
    db = Database(paths.database).init()
    yield db, paths
    db.close()


def make_window(qtbot, env):
    from fortnite_coach.ui.main_window import MainWindow

    create_app([])
    w = MainWindow(*env)
    qtbot.addWidget(w)
    w.show()
    return w


@pytest.fixture
def window(qtbot, env):
    get_translator().set_language("he")
    yield make_window(qtbot, env)
    get_translator().set_language("he")


def test_startup_shows_dashboard(window):
    assert window.current_key == "dashboard"
    assert len(NAV_KEYS) == 14


def test_every_nav_button_navigates(window, qtbot):
    for key in NAV_KEYS:
        qtbot.mouseClick(window.sidebar.buttons[key], Qt.MouseButton.LeftButton)
        assert window.current_key == key
        assert window.sidebar.buttons[key].isChecked()


def test_hebrew_is_rtl_by_default(window):
    assert QApplication.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert window.pages["dashboard"].title_label.text() == "לוח בקרה"


def test_switch_to_english_via_settings(window):
    combo = window.settings_page.lang_combo
    combo.setCurrentIndex(combo.findData("en"))
    assert QApplication.layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert window.pages["dashboard"].title_label.text() == "Dashboard"
    assert "Dashboard" in window.sidebar.buttons["dashboard"].text()


def test_no_fake_statistics_on_dashboard(window):
    get_translator().set_language("en")
    dash = window.pages["dashboard"]
    assert dash.tile_rating.value.text() == "Not enough data"
    assert dash.tile_sessions.value.text() == "0"
    for _name, value in dash.skill_rows.values():
        assert value.text() == "Not enough data"


def test_gemini_shown_as_not_configured(window):
    get_translator().set_language("en")
    assert "API key not configured" in window.sidebar.status.text()
    assert not GeminiStatus.NOT_CONFIGURED.can_analyze


def test_no_page_is_left_in_development(window):
    # every page in the sidebar is functional now; none may show an "in development" badge
    for key, page in window.pages.items():
        assert not page.dev_badge.isVisibleTo(page), key


def test_all_icons_render(qtbot):
    create_app([])
    for name in icons.available():
        assert not icons.pixmap(name, "#ffffff", 20).isNull()


def test_stylesheet_tokens_fully_resolved():
    import re

    from fortnite_coach.ui.theme import stylesheet

    assert not re.search(r"@[A-Z]", stylesheet())


def test_language_persists_after_restart(qtbot, env):
    w = make_window(qtbot, env)
    w.set_language("en")
    w.close()
    get_translator().set_language("he")  # simulate a fresh process
    w2 = make_window(qtbot, env)
    assert get_translator().language == "en"
    assert w2.pages["dashboard"].title_label.text() == "Dashboard"
    get_translator().set_language("he")


def test_dashboard_reflects_stored_results(window, env):
    from tests.helpers import add_test_report

    db, _ = env
    add_test_report(db, "f1", {"aim": (72, 2), "building": (41, 1), "editing": (55, 1)})  # TEST DATA
    window.refresh_data()
    get_translator().set_language("en")
    dash = window.pages["dashboard"]
    assert dash.tile_sessions.value.text() == "1"
    assert dash.tile_rating.value.text() == "56"
    assert dash.tile_strongest.value.text() == "Aim"
    assert dash.tile_weakest.value.text() == "Building"
    assert dash.skill_rows["movement"][1].text() == "Not enough data"


def test_delete_all_from_settings(window, env, monkeypatch):
    from tests.helpers import add_test_report

    db, _ = env
    add_test_report(db, "f1", {"aim": (72, 2)})  # TEST DATA
    window.refresh_data()
    page = window.settings_page
    monkeypatch.setattr(page, "confirm", lambda *a: False)
    page.delete_all_btn.click()
    assert window.pages["dashboard"].stats.analyzed_sessions == 1  # cancelled -> nothing deleted
    monkeypatch.setattr(page, "confirm", lambda *a: True)
    page.delete_all_btn.click()
    assert window.pages["dashboard"].stats.analyzed_sessions == 0


def test_profile_name_saved_to_database(window, env):
    from fortnite_coach.db.repositories import profile_repo

    page = window.pages["profile"]
    page.name_edit.setText("Avi")
    page.save_btn.click()
    assert profile_repo.get_or_create_profile(env[0]).display_name == "Avi"


def test_movement_page_uses_taxonomy(window):
    get_translator().set_language("en")
    page = window.pages["movement"]
    texts = [lbl.text() for lbl in page.criteria_labels]
    assert any("Strafing" in t for t in texts)
    assert page.mistake_labels  # tracked mistakes listed


def test_profile_strengths_need_evidence(window, env):
    from tests.helpers import add_test_report

    get_translator().set_language("en")
    page = window.pages["profile"]
    assert "Not enough data" in page.strengths_body.text()
    add_test_report(env[0], "f9", {"aim": (80, 2), "building": (40, 1)})  # TEST DATA
    window.refresh_data()
    assert page.strengths_body.text().startswith("Aim")
    assert page.weak_body.text().startswith("Building")
