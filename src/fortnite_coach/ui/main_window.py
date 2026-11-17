from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QStackedWidget, QWidget

from fortnite_coach.ai.status import GeminiStatus
from fortnite_coach.config.paths import AppPaths
from fortnite_coach.db.engine import Database
from fortnite_coach.db.repositories import data_repo, session_repo, settings_repo, stats_repo
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
    def __init__(self, db: Database, paths: AppPaths) -> None:
        super().__init__()
        self.db = db
        self.paths = paths
        self.settings = settings_repo.load_settings(db)
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
        self.settings_page.language_selected.connect(self.set_language)
        self.settings_page.clear_cache_requested.connect(self._clear_cache)
        self.settings_page.delete_all_requested.connect(self._delete_all)
        get_translator().on_change(self._on_language_changed)
        get_translator().set_language(self.settings.language.value)

        self.set_gemini_status(GeminiStatus.NOT_CONFIGURED)
        self.refresh_data()
        self.retranslate()
        self.navigate("dashboard")

    # ---- data -------------------------------------------------------------
    def refresh_data(self) -> None:
        """Reload everything shown from the database (called after any data change)."""
        self.pages["dashboard"].refresh(stats_repo.dashboard_stats(self.db))
        self.settings_page.set_data_info(session_repo.counts(self.db), str(self.paths.root))

    def set_language(self, language: str) -> None:
        from fortnite_coach.config.settings import Language

        self.settings.language = Language(language)
        settings_repo.save_settings(self.db, self.settings)
        get_translator().set_language(language)

    def _on_language_changed(self, _lang: str) -> None:
        # Translator listeners outlive closed windows in tests; ignore deleted widgets.
        try:
            self.retranslate()
        except RuntimeError:
            pass

    def _clear_cache(self) -> None:
        freed = data_repo.clear_cache(self.paths.cache_dir)
        self.paths.ensure()
        self.settings_page.show_data_feedback(tr("settings.cache_cleared", mb=f"{freed / 1_048_576:.1f}"))

    def _delete_all(self) -> None:
        data_repo.delete_all_analysis_data(self.db)
        self.refresh_data()
        self.settings_page.show_data_feedback(tr("settings.data_deleted"))

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
