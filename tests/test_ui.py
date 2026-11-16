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
def window(qtbot):
    create_app([])
    get_translator().set_language("he")
    from fortnite_coach.ui.main_window import MainWindow

    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    yield w
    get_translator().set_language("he")


def test_startup_shows_dashboard(window):
    assert window.current_key == "dashboard"
    assert len(NAV_KEYS) == 12


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


def test_unfinished_pages_are_marked(window):
    for key in ("gameplay", "training_sessions", "training_plan", "progress", "history"):
        assert window.pages[key].dev_badge.isVisibleTo(window.pages[key])
    assert not window.pages["dashboard"].dev_badge.isVisibleTo(window.pages["dashboard"])


def test_all_icons_render(qtbot):
    create_app([])
    for name in icons.available():
        assert not icons.pixmap(name, "#ffffff", 20).isNull()


def test_stylesheet_tokens_fully_resolved():
    import re

    from fortnite_coach.ui.theme import stylesheet

    assert not re.search(r"@[A-Z]", stylesheet())
