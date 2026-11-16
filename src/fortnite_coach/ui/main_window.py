from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QStackedWidget, QWidget

from fortnite_coach.ai.status import GeminiStatus
from fortnite_coach.core.skills import SKILL_PAGES
from fortnite_coach.i18n.translator import get_translator, tr
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.pages.dashboard import DashboardPage
from fortnite_coach.ui.pages.settings_page import SettingsPage
from fortnite_coach.ui.pages.simple_pages import (
    GameplayAnalysisPage,
    HistoryPage,
    ProgressPage,
    TrainingPlanPage,
    TrainingSessionsPage,
)
from fortnite_coach.ui.pages.skill_page import SkillPage
from fortnite_coach.ui.sidebar import NAV_KEYS, Sidebar


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(1100, 700)
        self.resize(1360, 860)
        root = QWidget(objectName="Root")
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.sidebar = Sidebar()
        self.stack = QStackedWidget()
        lay.addWidget(self.sidebar)
        lay.addWidget(self.stack, 1)

        self.settings_page = SettingsPage()
        self.pages: dict[str, BasePage] = {
            "dashboard": DashboardPage(),
            "gameplay": GameplayAnalysisPage(),
            "training_sessions": TrainingSessionsPage(),
            **{s.value: SkillPage(s) for s in SKILL_PAGES},
            "training_plan": TrainingPlanPage(),
            "progress": ProgressPage(),
            "history": HistoryPage(),
            "settings": self.settings_page,
        }
        assert list(self.pages) == NAV_KEYS, "page order must match the sidebar"
        for page in self.pages.values():
            self.stack.addWidget(page)

        self.sidebar.navigated.connect(self.navigate)
        self.settings_page.language_selected.connect(get_translator().set_language)
        get_translator().on_change(lambda _lang: self.retranslate())

        self.set_gemini_status(GeminiStatus.NOT_CONFIGURED)
        self.retranslate()
        self.navigate("dashboard")

    @property
    def current_key(self) -> str:
        return NAV_KEYS[self.stack.currentIndex()]

    def navigate(self, key: str) -> None:
        self.stack.setCurrentWidget(self.pages[key])
        self.sidebar.set_current(key)

    def set_gemini_status(self, status: GeminiStatus) -> None:
        self.sidebar.set_gemini_status(status)
        self.settings_page.set_gemini_status(status)

    def retranslate(self) -> None:
        t = get_translator()
        direction = Qt.LayoutDirection.RightToLeft if t.is_rtl else Qt.LayoutDirection.LeftToRight
        QApplication.setLayoutDirection(direction)
        self.setWindowTitle(tr("app.title"))
        self.sidebar.retranslate()
        for page in self.pages.values():
            page.retranslate()
