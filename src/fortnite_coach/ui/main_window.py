from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QStackedWidget, QWidget

from fortnite_coach.ai.key_store import KeyStore
from fortnite_coach.ai.status import GeminiStatus, current_status
from fortnite_coach.config.settings import AppSettings
from fortnite_coach.recording.controller import RecordingController
from fortnite_coach.recording.hotkeys import HotkeyError, HotkeyManager
from fortnite_coach.config.paths import AppPaths
from fortnite_coach.db.engine import Database
from fortnite_coach.db.repositories import data_repo, profile_repo, session_repo, settings_repo, stats_repo
from fortnite_coach.core.skills import SKILL_PAGES
from fortnite_coach.i18n.translator import get_translator, tr
from fortnite_coach.ui.context import AppContext
from fortnite_coach.ui.pages.analysis_page import AnalysisPage
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.pages.dashboard import DashboardPage
from fortnite_coach.ui.pages.profile_page import ProfilePage
from fortnite_coach.ui.pages.settings_page import SettingsPage
from fortnite_coach.ui.pages.simple_pages import (
    HistoryPage,
    ProgressPage,
    TrainingPlanPage,
)
from fortnite_coach.ui.pages.skill_page import SkillPage
from fortnite_coach.ui.sidebar import NAV_KEYS, Sidebar


class MainWindow(QMainWindow):
    def __init__(self, db: Database, paths: AppPaths, *, key_store: KeyStore | None = None,
                 recording_source: str | None = None) -> None:
        super().__init__()
        self.db = db
        self.paths = paths
        self.settings = settings_repo.load_settings(db)
        self.key_store = key_store or KeyStore()
        self.recording = RecordingController(paths.logs_dir, lambda: self.settings, source_override=recording_source)
        self.ctx = AppContext(
            db=db, paths=paths, settings=lambda: self.settings, save_settings=self._save_settings,
            recording=self.recording, key_store=self.key_store, gemini_status=self.gemini_status,
        )
        self.hotkeys = HotkeyManager(QApplication.instance())
        self.hotkey_errors: list[str] = []
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

        self.settings_page = SettingsPage(self.ctx)
        self.pages: dict[str, BasePage] = {
            "dashboard": DashboardPage(),
            "profile": ProfilePage(),
            "gameplay": AnalysisPage(self.ctx, training=False),
            "training_sessions": AnalysisPage(self.ctx, training=True),
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
        self.pages["profile"].name_saved.connect(self._save_profile_name)
        self.pages["profile"].set_profile(profile_repo.get_or_create_profile(db).display_name)
        self.settings_page.language_selected.connect(self.set_language)
        self.settings_page.clear_cache_requested.connect(self._clear_cache)
        self.settings_page.delete_all_requested.connect(self._delete_all)
        self.settings_page.key_changed.connect(self.refresh_gemini_status)
        self.settings_page.recording_settings_saved.connect(self.register_hotkeys)
        for key in ("gameplay", "training_sessions"):
            self.pages[key].video_imported.connect(self.refresh_data)
        self.recording.state_changed.connect(lambda _s: self._render_recording_indicator())
        self.recording.tick.connect(lambda _t: self._render_recording_indicator())
        self.register_hotkeys()
        get_translator().on_change(self._on_language_changed)
        get_translator().set_language(self.settings.language.value)

        self.refresh_gemini_status()
        self.refresh_data()
        self.retranslate()
        self.navigate("dashboard")

    # ---- gemini / recording ------------------------------------------------
    def gemini_status(self) -> GeminiStatus:
        # The connection test arrives in Phase 6; until then a saved key is "untested".
        return current_status(self.key_store.has_key(), None)

    def refresh_gemini_status(self) -> None:
        self.set_gemini_status(self.gemini_status())
        for key in ("gameplay", "training_sessions"):
            self.pages[key].refresh_status()

    def _save_settings(self, settings: AppSettings) -> None:
        self.settings = settings
        settings_repo.save_settings(self.db, settings)

    def register_hotkeys(self) -> None:
        """(Re)register global start/stop hotkeys from settings. Windows only."""
        self.hotkeys.unregister_all()
        self.hotkey_errors = []
        rec = self.settings.recording
        if not rec.hotkeys_enabled:
            return
        for combo, action in ((rec.hotkey_start, self.recording.start), (rec.hotkey_stop, self.recording.stop)):
            try:
                if not self.hotkeys.register(combo, action):
                    self.hotkey_errors.append(combo)
            except HotkeyError:
                self.hotkey_errors.append(combo)

    def _render_recording_indicator(self) -> None:
        rec = self.recording
        self.sidebar.set_recording(rec.is_recording, rec.recorder.elapsed_s)
        title = tr("app.title")
        self.setWindowTitle(f"● REC  {title}" if rec.is_recording else title)

    def bring_to_front(self) -> None:
        """Called when the user launches the app a second time."""
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        if self.recording.is_recording:
            self.recording.stop()  # finalize the file instead of leaving ffmpeg orphaned
        self.hotkeys.unregister_all()
        super().closeEvent(event)

    # ---- data -------------------------------------------------------------
    def refresh_data(self) -> None:
        """Reload everything shown from the database (called after any data change)."""
        stats = stats_repo.dashboard_stats(self.db)
        self.pages["dashboard"].refresh(stats)
        self.pages["profile"].refresh(stats)
        for skill in SKILL_PAGES:
            self.pages[skill.value].refresh(stats)
        self.settings_page.set_data_info(session_repo.counts(self.db), str(self.paths.root))

    def _save_profile_name(self, name: str) -> None:
        profile = profile_repo.update_profile(self.db, display_name=name)
        self.pages["profile"].set_profile(profile.display_name)
        self.pages["profile"].show_saved()

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
        self.sidebar.retranslate()
        self._render_recording_indicator()
        for page in self.pages.values():
            page.retranslate()
