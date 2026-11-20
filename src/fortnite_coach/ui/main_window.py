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
from fortnite_coach.ui.pages.clips_page import ClipsPage
from fortnite_coach.ui.pages.dashboard import DashboardPage
from fortnite_coach.ui.pages.profile_page import ProfilePage
from fortnite_coach.ui.pages.settings_page import SettingsPage
from fortnite_coach.ui.pages.help_page import HelpPage
from fortnite_coach.ui.pages.history_page import HistoryPage
from fortnite_coach.ui.pages.progress_page import ProgressPage
from fortnite_coach.ui.pages.training_plan_page import TrainingPlanPage
from fortnite_coach.ui.pages.skill_page import SkillPage
from fortnite_coach.ui.sidebar import NAV_KEYS, Sidebar


class MainWindow(QMainWindow):
    def __init__(self, db: Database, paths: AppPaths, *, key_store: KeyStore | None = None,
                 recording_source: str | None = None, client_factory=None) -> None:
        from fortnite_coach.live.coach import LiveCoach
        from fortnite_coach.ui.overlay import TipOverlay

        super().__init__()
        self.db = db
        self.paths = paths
        self.settings = settings_repo.load_settings(db)
        self.key_store = key_store or KeyStore()
        self.recording = RecordingController(paths.logs_dir, lambda: self.settings, source_override=recording_source)
        self.client_factory = client_factory
        self.live = LiveCoach(lambda: self.settings, self.make_gemini_service, db,
                              gemini_ready=lambda: self.gemini_status() is GeminiStatus.CONNECTED,
                              source_override=recording_source)
        self.overlay = TipOverlay()
        self.live.tip.connect(self._show_tip)
        self.live.tip.connect(lambda _t: self._on_session_changed())
        self.live.stopped_with_error.connect(self._on_live_error)
        self.live.state_changed.connect(lambda _a: self._on_session_changed())
        self.ctx = AppContext(
            db=db, paths=paths, settings=lambda: self.settings, save_settings=self._save_settings,
            recording=self.recording, key_store=self.key_store, gemini_status=self.gemini_status,
            gemini_service=self.make_gemini_service, open_report=self.open_report, data_changed=self.refresh_data,
            live=self.live, start_session=self.start_session, stop_session=self.stop_session,
            preview_tip=self._show_tip,
        )
        self.hotkeys = HotkeyManager(QApplication.instance(), lambda: int(self.winId()))
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
            "clips": ClipsPage(self.ctx, self.open_clip),
            **{s.value: SkillPage(s) for s in SKILL_PAGES},
            "training_plan": TrainingPlanPage(self.ctx),
            "progress": ProgressPage(self.ctx),
            "history": HistoryPage(self.ctx),
            "help": HelpPage(self.ctx),
            "settings": self.settings_page,
        }
        assert list(self.pages) == NAV_KEYS, "page order must match the sidebar"
        for page in self.pages.values():
            self.stack.addWidget(page)
        from fortnite_coach.ui.widgets.onboarding import OnboardingCard

        self.onboarding = OnboardingCard(self.ctx, self.navigate)
        self.pages["dashboard"].content.insertWidget(1, self.onboarding)

        self.sidebar.navigated.connect(self.navigate)
        self.pages["profile"].name_saved.connect(self._save_profile_name)
        self.pages["profile"].set_profile(profile_repo.get_or_create_profile(db).display_name)
        self.settings_page.language_selected.connect(self.set_language)
        self.settings_page.clear_cache_requested.connect(self._clear_cache)
        self.settings_page.delete_all_requested.connect(self._delete_all)
        self.settings_page.key_changed.connect(self._on_key_changed)
        self.settings_page.test_requested.connect(self.run_connection_test)
        self.settings_page.gemini_settings_saved.connect(self.refresh_gemini_status)
        self.settings_page.recording_settings_saved.connect(self.register_hotkeys)
        for key in ("gameplay", "training_sessions"):
            self.pages[key].video_imported.connect(self.refresh_data)
        self.recording.capabilities_ready.connect(self._on_capabilities)
        self.recording.state_changed.connect(lambda _s: self._on_session_changed())
        self.recording.tick.connect(lambda _t: self._render_recording_indicator())
        self.register_hotkeys()
        from fortnite_coach.ui.tray import TrayController

        self.tray = TrayController(self.recording, self, live=self.live, start=self.start_session,
                                   stop=self.stop_session)
        self.tray.open_requested.connect(self.bring_to_front)
        self.tray.quit_requested.connect(self.quit_app)
        self._quitting = False
        self.quit_on_close = False
        for key in ("gameplay", "training_sessions"):
            self.pages[key].analysis_finished.connect(self._notify_if_background)
        get_translator().on_change(self._on_language_changed)
        get_translator().set_language(self.settings.language.value)

        self.refresh_gemini_status()
        self.refresh_data()
        self.retranslate()
        self.navigate("dashboard")

    # ---- gemini / recording ------------------------------------------------
    def gemini_status(self) -> GeminiStatus:
        return current_status(self.key_store.has_key(), self.settings.gemini.last_test_ok)

    def make_gemini_service(self):
        from fortnite_coach.ai.gemini_service import GeminiService

        g = self.settings.gemini
        return GeminiService(self.key_store.load, g.model, timeout_s=g.request_timeout_s, max_retries=g.max_retries,
                             client_factory=self.client_factory)

    def open_report(self, report_id: int, banner: str = "") -> None:
        self.refresh_data()
        self.pages["history"].show_report(report_id, banner)
        self.navigate("history")

    def _on_key_changed(self) -> None:
        g = self.settings.gemini.model_copy()
        g.last_test_ok, g.last_test_at, g.last_test_error = None, None, None  # a new key must be tested
        self.settings.gemini = g
        self._save_settings(self.settings)
        self.refresh_gemini_status()

    def run_connection_test(self) -> None:
        from fortnite_coach.ai.gemini_connection_test import test_connection
        from fortnite_coach.ai import usage_tracker
        from fortnite_coach.workers.task import run_task

        if self.settings_page.testing:
            return
        service = self.make_gemini_service()
        self.settings_page.set_testing(True)

        def done(result):
            g = self.settings.gemini.model_copy()
            g.last_test_ok, g.last_test_at, g.last_test_error = result.ok, result.tested_at, result.error_key
            g.last_test_detail = result.detail
            if result.available_models:
                g.available_models = result.available_models
            if result.picked_model:
                g.model = result.picked_model
                self.settings_page.model_picked_notice = result.picked_model
            self.settings.gemini = g
            self._save_settings(self.settings)
            usage_tracker.record(self.db, model=g.model, kind="connection_test", success=result.ok,
                                 error_code=result.error_key)
            self.settings_page.set_testing(False)
            self.refresh_gemini_status()

        def failed(err):
            self.settings_page.set_testing(False)
            self.refresh_gemini_status()

        may_pick = not self.settings.gemini.model_user_chosen
        run_task(lambda: test_connection(service, may_pick=may_pick), done, failed)

    def refresh_gemini_status(self) -> None:
        self.set_gemini_status(self.gemini_status())
        self.settings_page.set_gemini_status(self.gemini_status())
        self.settings_page.refresh_cards()
        if hasattr(self, "onboarding"):
            self.onboarding.render()
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
        for combo, action in ((rec.hotkey_start, self.start_session), (rec.hotkey_stop, self.stop_session),
                              (self.settings.live.hotkey, self.live.toggle)):
            try:
                if not self.hotkeys.register(combo, action):
                    self.hotkey_errors.append(combo)
            except HotkeyError:
                self.hotkey_errors.append(combo)
        self.recording.hotkey_errors = list(self.hotkey_errors)

    # ---- sessions: record / record + live / live only ------------------------
    def session_active(self) -> bool:
        return self.recording.is_recording or self.live.active

    def start_session(self) -> None:
        """Start what the player chose on the record card (button, hotkey or tray)."""
        mode = self.settings.recording.start_mode
        if mode in ("record", "record_live"):
            self.recording.start()
        if mode in ("live", "record_live"):
            self.live.start()

    def stop_session(self) -> None:
        if self.live.active:
            self.live.stop()
        if self.recording.is_recording:
            self.recording.stop()

    def open_clip(self, path: str) -> None:
        self.pages["gameplay"].load_path(path)
        self.navigate("gameplay")

    def _show_tip(self, text: str) -> None:
        self.overlay.monitor_index = self.settings.recording.monitor_index
        self.overlay.show_tip(text, self.settings.live.show_seconds)

    def _on_live_error(self, key: str) -> None:
        msg = tr("live.stopped", reason=tr(key))
        self._show_tip(msg)  # visible in-game, top-left
        self.tray.notify(msg)
        self._on_session_changed()

    def _on_session_changed(self) -> None:
        self._render_recording_indicator()
        for key in ("gameplay", "training_sessions"):
            self.pages[key]._render_recording()

    def _on_capabilities(self, caps) -> None:
        if caps is not None and not self.settings.hardware_checked:
            self.settings.hardware_checked = True
            self._save_settings(self.settings)
            self.refresh_data()

    def _render_recording_indicator(self) -> None:
        rec = self.recording
        live = self.live.active
        self.sidebar.set_recording(rec.is_recording, rec.recorder.elapsed_s, live)
        title = tr("app.title")
        prefix = ("● REC  " if rec.is_recording else "") + ("◆ LIVE  " if live else "")
        self.setWindowTitle(prefix + title)

    def bring_to_front(self) -> None:
        """Called when the user launches the app a second time."""
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def _notify_if_background(self, text: str) -> None:
        if not self.isActiveWindow():
            self.tray.notify(text)

    def keeps_running_in_tray(self) -> bool:
        return (self.settings.close_to_tray and self.settings.recording.hotkeys_enabled
                and self.tray.available and not self._quitting)

    def quit_app(self) -> None:
        self._quitting = True
        self.close()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        if self.keeps_running_in_tray():
            # Keep running next to the clock so recording hotkeys work during a match.
            event.ignore()
            self.hide()
            if not self.tray.told_about_tray:
                self.tray.told_about_tray = True
                self.tray.notify(tr("tray.still_running"))
            return
        self.live.stop()
        self.overlay.hide()
        if self.recording.is_recording:
            self.recording.stop()  # finalize the file instead of leaving ffmpeg orphaned
        self.hotkeys.unregister_all()
        self.tray.hide()
        super().closeEvent(event)
        if self.quit_on_close:  # set by app.run(): the real app exits when the window really closes
            QApplication.quit()

    # ---- data -------------------------------------------------------------
    def refresh_data(self) -> None:
        """Reload everything shown from the database (called after any data change)."""
        from fortnite_coach.db.repositories import report_repo

        stats = stats_repo.dashboard_stats(self.db)
        lv = report_repo.levels(self.db)
        repeated = report_repo.repeated_mistakes(self.db)
        from fortnite_coach.db.repositories import progress_repo

        self.pages["dashboard"].refresh(stats, lv, report_repo.list_reports(self.db, 5), repeated,
                                        progress_repo.periods(self.db))
        self.pages["profile"].refresh(stats, lv, repeated)
        for skill in SKILL_PAGES:
            self.pages[skill.value].refresh(stats, lv.skills.get(skill.value),
                                            report_repo.findings_for_skill(self.db, skill.value))
        self.pages["history"].refresh()
        self.pages["training_plan"].reload()
        self.pages["progress"].reload()
        self.settings_page.set_data_info(session_repo.counts(self.db), str(self.paths.root))
        self.settings_page.refresh_cards()
        if hasattr(self, "onboarding"):
            self.onboarding.render()

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
        """Delete local analysis data; when connected, also ask Google to delete uploaded videos first."""
        from fortnite_coach.workers.task import run_task

        names = data_repo.uploaded_file_names(self.db)

        def finish_local(remote: tuple[int, int] | None) -> None:
            data_repo.delete_all_analysis_data(self.db)
            self.refresh_data()
            msg = tr("settings.data_deleted")
            if remote is not None:
                msg += " " + tr("settings.remote_deleted", ok=remote[0], failed=remote[1])
            elif names:
                msg += " " + tr("settings.remote_expire")
            self.settings_page.show_data_feedback(msg)

        if names and self.gemini_status() is GeminiStatus.CONNECTED:
            service = self.make_gemini_service()
            self.settings_page.show_data_feedback(tr("common.loading"))
            run_task(lambda: data_repo.delete_uploaded_files(self.db, service), finish_local,
                     lambda _e: finish_local(None))
        else:
            finish_local(None)

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
        if hasattr(self, "tray"):
            self.tray.render()
        for page in self.pages.values():
            page.retranslate()
        if hasattr(self, "onboarding"):
            self.onboarding.render()
