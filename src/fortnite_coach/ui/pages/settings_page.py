from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QWidget

from fortnite_coach.ai.status import GeminiStatus
from fortnite_coach.i18n.translator import get_translator, tr
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.ui.widgets.status_pill import StatusPill


class SettingsPage(BasePage):
    page_key = "settings"
    language_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.lang_card = Card()
        form = QFormLayout()
        self.lang_label = QLabel()
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("עברית", "he")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.currentIndexChanged.connect(self._on_lang)
        form.addRow(self.lang_label, self.lang_combo)
        self.lang_card.body.addLayout(form)
        self.content.addWidget(self.lang_card)

        self.gemini_card = Card()
        self.gemini_status = StatusPill()
        self.gemini_info = QLabel(objectName="StatHint")
        self.gemini_info.setWordWrap(True)
        self.gemini_card.body.addWidget(self.gemini_status)
        self.gemini_card.body.addWidget(self.gemini_info)
        self.content.addWidget(self.gemini_card)
        self._status = GeminiStatus.NOT_CONFIGURED

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
        for w in (self.data_counts, self.data_path):
            self.data_card.body.addWidget(w)
        self.data_card.body.addLayout(btns)
        self.data_card.body.addWidget(self.data_feedback)
        self.content.addWidget(self.data_card)
        self.clear_cache_btn.clicked.connect(self._on_clear_cache)
        self.delete_all_btn.clicked.connect(self._on_delete_all)
        self._counts = {"videos": 0, "sessions": 0, "reports": 0}
        self._data_dir = ""
        self.finish()

    # Data management signals are handled by MainWindow (it owns the database).
    clear_cache_requested = Signal()
    delete_all_requested = Signal()

    def set_data_info(self, counts: dict[str, int], data_dir: str) -> None:
        self._counts = counts
        self._data_dir = data_dir
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

    def _on_lang(self, _index: int) -> None:
        self.language_selected.emit(self.lang_combo.currentData())

    def set_gemini_status(self, status: GeminiStatus) -> None:
        self._status = status
        self.gemini_status.set_state(status.pill_state, tr(status.i18n_key))

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
        self.gemini_card.set_title(tr("settings.gemini"), tr("settings.gemini_sub"))
        self.set_gemini_status(self._status)
        self.gemini_info.setText(tr("settings.gemini_pending"))
        self.data_card.set_title(tr("settings.data"), tr("settings.data_sub"))
        self.clear_cache_btn.setText(tr("settings.clear_cache"))
        self.delete_all_btn.setText(tr("settings.delete_all"))
        self.clear_cache_btn.setToolTip(tr("settings.clear_cache_tip"))
        self.delete_all_btn.setToolTip(tr("settings.delete_all_tip"))
        self._render_data()
