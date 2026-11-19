from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QWidget,
)

from fortnite_coach.ai.key_store import KeyStoreError, looks_like_gemini_key, mask
from fortnite_coach.ai.status import GeminiStatus
from fortnite_coach.i18n.translator import get_translator, tr
from fortnite_coach.recording.hotkeys import HotkeyError, is_supported as hotkeys_supported, parse_hotkey
from fortnite_coach.recording.recorder import default_output_dir
from fortnite_coach.ui.context import AppContext
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.ui.widgets.status_pill import StatusPill


class SettingsPage(BasePage):
    page_key = "settings"
    language_selected = Signal(str)
    clear_cache_requested = Signal()
    delete_all_requested = Signal()
    key_changed = Signal()
    test_requested = Signal()
    gemini_settings_saved = Signal()
    recording_settings_saved = Signal()

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx

        # ---- language ----
        self.lang_card = Card()
        form = QFormLayout()
        self.lang_label = QLabel()
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("עברית", "he")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.currentIndexChanged.connect(lambda _i: self.language_selected.emit(self.lang_combo.currentData()))
        form.addRow(self.lang_label, self.lang_combo)
        self.lang_card.body.addLayout(form)
        self.content.addWidget(self.lang_card)

        # ---- Gemini API key ----
        self.gemini_card = Card()
        self.gemini_status = StatusPill()
        self.gemini_card.body.addWidget(self.gemini_status)
        key_row = QHBoxLayout()
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setObjectName("ApiKeyInput")
        # Never offer the key to input-method history/autocomplete.
        self.key_edit.setInputMethodHints(Qt.InputMethodHint.ImhHiddenText | Qt.InputMethodHint.ImhNoPredictiveText
                                          | Qt.InputMethodHint.ImhSensitiveData)
        self.show_key_btn = QPushButton()
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.toggled.connect(self._toggle_show)
        self.save_key_btn = QPushButton(objectName="PrimaryButton")
        self.save_key_btn.clicked.connect(self._save_key)
        self.delete_key_btn = QPushButton(objectName="DangerButton")
        self.delete_key_btn.clicked.connect(self._delete_key)
        key_row.addWidget(self.key_edit, 1)
        key_row.addWidget(self.show_key_btn)
        key_row.addWidget(self.save_key_btn)
        key_row.addWidget(self.delete_key_btn)
        self.gemini_card.body.addLayout(key_row)
        self.key_feedback = QLabel()
        self.key_feedback.setWordWrap(True)
        self.gemini_info = QLabel(objectName="StatHint")
        self.gemini_info.setWordWrap(True)
        self.gemini_guide = QLabel(objectName="StatHint")
        self.gemini_guide.setWordWrap(True)
        self.gemini_guide.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.gemini_guide.setOpenExternalLinks(True)
        test_row = QHBoxLayout()
        self.test_btn = QPushButton(objectName="PrimaryButton")
        self.test_btn.clicked.connect(self.test_requested)
        self.test_result = QLabel()
        self.test_result.setWordWrap(True)
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_result, 1)
        self.gemini_card.body.addLayout(test_row)
        gform = QFormLayout()
        gform.setHorizontalSpacing(16)
        self.model_label, self.limit_label, self.minutes_label = QLabel(), QLabel(), QLabel()
        self.model_combo = QComboBox()
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 1000)
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(1, 60)
        gform.addRow(self.model_label, self.model_combo)
        gform.addRow(self.limit_label, self.limit_spin)
        gform.addRow(self.minutes_label, self.minutes_spin)
        self.gemini_card.body.addLayout(gform)
        grow = QHBoxLayout()
        self.gemini_save_btn = QPushButton()
        self.gemini_save_btn.clicked.connect(self._save_gemini)
        self.usage_label = QLabel(objectName="StatHint")
        grow.addWidget(self.gemini_save_btn)
        grow.addWidget(self.usage_label, 1)
        self.gemini_card.body.addLayout(grow)
        self.testing = False
        for w in (self.key_feedback, self.gemini_info, self.gemini_guide):
            self.gemini_card.body.addWidget(w)
        self.content.addWidget(self.gemini_card)
        self._key_msg: tuple[str, str] | None = None  # (i18n key, "ok"|"error")

        # ---- recording ----
        self.rec_card = Card()
        rform = QFormLayout()
        rform.setHorizontalSpacing(16)
        self.rec_labels = {k: QLabel() for k in ("folder", "resolution", "fps", "quality", "encoder", "audio",
                                                 "hotkey_start", "hotkey_stop")}
        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_btn = QPushButton()
        self.folder_btn.clicked.connect(self._choose_folder)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.folder_btn)
        self.res_combo = QComboBox()
        for r in ("native", "1440p", "1080p", "720p"):
            self.res_combo.addItem("", r)
        self.fps_combo = QComboBox()
        for f in (30, 60):
            self.fps_combo.addItem(str(f), f)
        self.quality_combo = QComboBox()
        for q in ("low", "medium", "high"):
            self.quality_combo.addItem("", q)
        self.encoder_combo = QComboBox()
        self.audio_combo = QComboBox()
        self.hk_start = QLineEdit()
        self.hk_stop = QLineEdit()
        self.hk_enabled = QCheckBox()
        rform.addRow(self.rec_labels["folder"], folder_row)
        rform.addRow(self.rec_labels["resolution"], self.res_combo)
        rform.addRow(self.rec_labels["fps"], self.fps_combo)
        rform.addRow(self.rec_labels["quality"], self.quality_combo)
        rform.addRow(self.rec_labels["encoder"], self.encoder_combo)
        rform.addRow(self.rec_labels["audio"], self.audio_combo)
        rform.addRow(self.rec_labels["hotkey_start"], self.hk_start)
        rform.addRow(self.rec_labels["hotkey_stop"], self.hk_stop)
        rform.addRow("", self.hk_enabled)
        self.rec_card.body.addLayout(rform)
        rbtns = QHBoxLayout()
        self.rec_save_btn = QPushButton(objectName="PrimaryButton")
        self.rec_save_btn.clicked.connect(self._save_recording)
        self.detect_btn = QPushButton()
        self.detect_btn.clicked.connect(ctx.recording.detect)
        rbtns.addWidget(self.rec_save_btn)
        rbtns.addWidget(self.detect_btn)
        rbtns.addStretch(1)
        self.rec_card.body.addLayout(rbtns)
        self.rec_feedback = QLabel()
        self.rec_feedback.setWordWrap(True)
        self.hw_info = QLabel(objectName="StatHint")
        self.hw_info.setWordWrap(True)
        self.rec_card.body.addWidget(self.rec_feedback)
        self.rec_card.body.addWidget(self.hw_info)
        self.content.addWidget(self.rec_card)
        self._rec_msg: tuple[str, dict] | None = None
        ctx.recording.capabilities_ready.connect(lambda _c: self._render_recording())

        # ---- data ----
        self.data_card = Card()
        self.data_counts = QLabel()
        self.data_path = QLabel(objectName="StatHint")
        self.data_path.setWordWrap(True)
        self.data_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        btns = QHBoxLayout()
        self.clear_cache_btn = QPushButton()
        self.delete_all_btn = QPushButton(objectName="DangerButton")
        btns.addWidget(self.clear_cache_btn)
        btns.addWidget(self.delete_all_btn)
        btns.addStretch(1)
        self.data_feedback = QLabel(objectName="StatHint")
        self.data_card.body.addWidget(self.data_counts)
        self.data_card.body.addWidget(self.data_path)
        self.data_card.body.addLayout(btns)
        self.data_card.body.addWidget(self.data_feedback)
        self.content.addWidget(self.data_card)
        self.clear_cache_btn.clicked.connect(self._on_clear_cache)
        self.delete_all_btn.clicked.connect(self._on_delete_all)
        self._counts = {"videos": 0, "sessions": 0, "reports": 0}
        self._data_dir = ""
        from fortnite_coach.ui.pages.settings_cards import AboutCard, KnowledgeCard, UsageCard

        self.usage_card = UsageCard(ctx)
        self.knowledge_card = KnowledgeCard(ctx)
        self.about_card = AboutCard(ctx)
        for c in (self.usage_card, self.knowledge_card, self.about_card):
            self.content.addWidget(c)
        self._load_recording_fields()
        self.finish()

    def refresh_cards(self) -> None:
        for c in (self.usage_card, self.knowledge_card, self.about_card):
            c.render()

    # ================= Gemini key =================
    def _toggle_show(self, shown: bool) -> None:
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password)
        self.show_key_btn.setText(tr("apikey.hide") if shown else tr("apikey.show"))

    def _save_key(self) -> None:
        try:
            self.ctx.key_store.save(self.key_edit.text())
        except KeyStoreError as e:
            self._key_msg = (e.i18n_key, "error")
        else:
            warn = not looks_like_gemini_key(self.key_edit.text().strip())
            self._key_msg = ("apikey.saved_unusual" if warn else "apikey.saved", "ok")
            self.key_edit.clear()  # the key does not stay in the widget
            self.show_key_btn.setChecked(False)
            self.key_changed.emit()
        self._render_gemini()

    def _delete_key(self) -> None:
        if not self.ctx.key_store.has_key():
            return
        if self.confirm(tr("apikey.delete"), tr("apikey.delete_confirm")):
            try:
                self.ctx.key_store.delete()
                self._key_msg = ("apikey.deleted", "ok")
            except KeyStoreError as e:
                self._key_msg = (e.i18n_key, "error")
            self.key_changed.emit()
            self._render_gemini()

    def set_gemini_status(self, status: GeminiStatus) -> None:
        self._render_gemini(status)

    def set_testing(self, testing: bool) -> None:
        self.testing = testing
        self._render_gemini()

    def _save_gemini(self) -> None:
        settings = self.ctx.settings()
        g = settings.gemini.model_copy()
        model = self.model_combo.currentData()
        if model and model != g.model:
            g.model = model
            g.last_test_ok = None  # a different model must be tested again
        settings.gemini = g
        lim = settings.limits.model_copy()
        lim.max_requests_per_day = self.limit_spin.value()
        lim.max_video_seconds = self.minutes_spin.value() * 60
        settings.limits = lim
        self.ctx.save_settings(settings)
        self._key_msg = ("settings.gemini_saved", "ok")
        self.gemini_settings_saved.emit()
        self._render_gemini()

    def _render_gemini(self, status: GeminiStatus | None = None) -> None:
        status = status or self.ctx.gemini_status()
        self.gemini_card.set_title(tr("settings.gemini"), tr("settings.gemini_sub"))
        self.gemini_status.set_state(status.pill_state, tr(status.i18n_key))
        stored = self.ctx.key_store.load()
        self.key_edit.setPlaceholderText(tr("apikey.placeholder_saved", masked=mask(stored)) if stored
                                         else tr("apikey.placeholder"))
        self.show_key_btn.setText(tr("apikey.hide") if self.show_key_btn.isChecked() else tr("apikey.show"))
        self.save_key_btn.setText(tr("common.save"))
        self.delete_key_btn.setText(tr("apikey.delete"))
        self.delete_key_btn.setEnabled(bool(stored))
        if self._key_msg:
            key, kind = self._key_msg
            self.key_feedback.setText(("✓  " if kind == "ok" else "⚠  ") + tr(key))
        else:
            self.key_feedback.setText("")
        backend = self.ctx.key_store.backend_available()
        info = [tr("apikey.where") if backend else tr("apikey.err_no_backend")]
        info.append(tr("apikey.status_explain." + status.value))
        info.append(tr("apikey.free_tier"))
        self.gemini_info.setText("\n".join(info))
        self.gemini_guide.setText(tr("apikey.guide"))
        from fortnite_coach.ai import usage_tracker
        from fortnite_coach.ai.gemini_config import ALLOWED_MODELS

        g = self.ctx.settings().gemini
        lim = self.ctx.settings().limits
        self.test_btn.setText(tr("apikey.testing") if self.testing else tr("apikey.test"))
        self.test_btn.setEnabled(bool(stored) and not self.testing)
        if g.last_test_at:
            res = tr("apikey.test_ok", at=g.last_test_at.replace("T", " ")[:16]) if g.last_test_ok else \
                "⚠  " + tr(g.last_test_error or "gemini.error")
        else:
            res = tr("apikey.test_never")
        self.test_result.setText(res)
        self.model_label.setText(tr("settings.model"))
        self.limit_label.setText(tr("settings.daily_limit"))
        self.minutes_label.setText(tr("settings.max_minutes"))
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for m in ALLOWED_MODELS:
            avail = (not g.available_models) or m in g.available_models
            self.model_combo.addItem(m + ("" if avail else "  " + tr("settings.model_unavailable")), m)
        self.model_combo.setCurrentIndex(max(0, self.model_combo.findData(g.model)))
        self.model_combo.blockSignals(False)
        self.limit_spin.setValue(lim.max_requests_per_day)
        self.minutes_spin.setValue(max(1, lim.max_video_seconds // 60))
        self.gemini_save_btn.setText(tr("common.save"))
        self.usage_label.setText(tr("settings.usage_today", used=usage_tracker.requests_today(self.ctx.db),
                                    limit=lim.max_requests_per_day, tokens=usage_tracker.tokens_today(self.ctx.db)))

    # ================= recording =================
    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("rec.folder"), self.folder_edit.text())
        if folder:
            self.folder_edit.setText(folder)

    def _load_recording_fields(self) -> None:
        rec = self.ctx.settings().recording
        self.folder_edit.setText(rec.output_dir or str(default_output_dir()))
        for combo, value in ((self.res_combo, rec.resolution), (self.fps_combo, rec.fps), (self.quality_combo, rec.quality)):
            i = combo.findData(value)
            combo.setCurrentIndex(max(0, i))
        self.hk_start.setText(rec.hotkey_start)
        self.hk_stop.setText(rec.hotkey_stop)
        self.hk_enabled.setChecked(rec.hotkeys_enabled)

    def _save_recording(self) -> None:
        settings = self.ctx.settings()
        rec = settings.recording.model_copy()
        start, stop = self.hk_start.text().strip(), self.hk_stop.text().strip()
        try:
            if parse_hotkey(start) == parse_hotkey(stop):
                raise HotkeyError("same")
        except HotkeyError:
            self._rec_msg = ("rec.err_hotkey", {})
            self._render_recording()
            return
        rec.output_dir = self.folder_edit.text().strip() or None
        rec.resolution = self.res_combo.currentData()
        rec.fps = self.fps_combo.currentData()
        rec.quality = self.quality_combo.currentData()
        rec.encoder = self.encoder_combo.currentData() or "auto"
        rec.audio_device = self.audio_combo.currentData() or None
        rec.hotkey_start, rec.hotkey_stop = start, stop
        rec.hotkeys_enabled = self.hk_enabled.isChecked()
        settings.recording = rec
        self.ctx.save_settings(settings)
        self._rec_msg = ("rec.settings_saved", {})
        self.recording_settings_saved.emit()
        self._render_recording()

    def set_audio_devices(self, devices: list[str]) -> None:
        self._audio_devices = devices
        self._render_recording()

    def _render_recording(self) -> None:
        rec = self.ctx.settings().recording
        caps = self.ctx.recording.caps
        self.rec_card.set_title(tr("rec.settings_title"), tr("rec.settings_sub"))
        for k, lbl in self.rec_labels.items():
            lbl.setText(tr(f"rec.field.{k}"))
        self.folder_btn.setText(tr("rec.browse"))
        for i in range(self.res_combo.count()):
            self.res_combo.setItemText(i, tr(f"rec.res.{self.res_combo.itemData(i)}"))
        for i in range(self.quality_combo.count()):
            self.quality_combo.setItemText(i, tr(f"rec.quality.{self.quality_combo.itemData(i)}"))
        # encoder choices: auto + encoders that passed a real test on this PC
        self.encoder_combo.blockSignals(True)
        self.encoder_combo.clear()
        self.encoder_combo.addItem(tr("rec.encoder_auto"), "auto")
        for e in (caps.working_encoders if caps else []):
            self.encoder_combo.addItem(e, e)
        self.encoder_combo.setCurrentIndex(max(0, self.encoder_combo.findData(rec.encoder)))
        self.encoder_combo.blockSignals(False)
        self.audio_combo.blockSignals(True)
        self.audio_combo.clear()
        self.audio_combo.addItem(tr("rec.audio_none"), "")
        for d in getattr(self, "_audio_devices", []):
            self.audio_combo.addItem(d, d)
        if rec.audio_device and self.audio_combo.findData(rec.audio_device) < 0:
            self.audio_combo.addItem(rec.audio_device, rec.audio_device)
        self.audio_combo.setCurrentIndex(max(0, self.audio_combo.findData(rec.audio_device or "")))
        self.audio_combo.blockSignals(False)
        self.hk_enabled.setText(tr("rec.hotkeys_enable") if hotkeys_supported() else tr("rec.hotkeys_windows_only"))
        self.hk_enabled.setEnabled(hotkeys_supported())
        self.rec_save_btn.setText(tr("common.save"))
        self.detect_btn.setText(tr("rec.detect"))
        self.rec_feedback.setText(tr(self._rec_msg[0], **self._rec_msg[1]) if self._rec_msg else "")
        rc = self.ctx.recording
        if rc.detecting:
            self.hw_info.setText(tr("rec.detecting"))
        elif caps is None:
            self.hw_info.setText(tr(rc.caps_error) if rc.caps_error else tr("rec.not_detected"))
        else:
            self.hw_info.setText(tr(
                "rec.hw_summary",
                version=caps.ffmpeg_version or "?",
                working=", ".join(caps.working_encoders) or tr("common.none"),
                untested=", ".join(e for e in caps.built_encoders if e not in caps.working_encoders) or tr("common.none"),
                capture=caps.capture_backend or tr("common.none"),
            ))

    # ================= data =================
    def set_data_info(self, counts: dict[str, int], data_dir: str) -> None:
        self._counts, self._data_dir = counts, data_dir
        self._render_data()

    def show_data_feedback(self, text: str) -> None:
        self.data_feedback.setText(text)

    def confirm(self, title: str, text: str) -> bool:
        """Ask the user; isolated so tests can replace it."""
        answer = QMessageBox.question(self, title, text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def _on_clear_cache(self) -> None:
        if self.confirm(tr("settings.clear_cache"), tr("settings.clear_cache_confirm")):
            self.clear_cache_requested.emit()

    def _on_delete_all(self) -> None:
        if self.confirm(tr("settings.delete_all"), tr("settings.delete_all_confirm")):
            self.delete_all_requested.emit()

    def _render_data(self) -> None:
        c = self._counts
        self.data_counts.setText(tr("settings.data_counts", sessions=c["sessions"], reports=c["reports"], videos=c["videos"]))
        self.data_path.setText(tr("settings.data_path", path=self._data_dir))

    # ================= i18n =================
    def retranslate(self) -> None:
        super().retranslate()
        lang = get_translator().language
        idx = self.lang_combo.findData(lang)
        if idx >= 0 and idx != self.lang_combo.currentIndex():
            self.lang_combo.blockSignals(True)
            self.lang_combo.setCurrentIndex(idx)
            self.lang_combo.blockSignals(False)
        self.lang_card.set_title(tr("settings.language"))
        self.lang_label.setText(tr("settings.language_label"))
        self._render_gemini()
        self._render_recording()
        self.data_card.set_title(tr("settings.data"), tr("settings.data_sub"))
        self.clear_cache_btn.setText(tr("settings.clear_cache"))
        self.delete_all_btn.setText(tr("settings.delete_all"))
        self.clear_cache_btn.setToolTip(tr("settings.clear_cache_tip"))
        self.delete_all_btn.setToolTip(tr("settings.delete_all_tip"))
        self._render_data()
        if hasattr(self, "about_card"):
            self.refresh_cards()
