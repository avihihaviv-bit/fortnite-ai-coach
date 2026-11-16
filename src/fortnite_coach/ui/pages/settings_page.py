from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QWidget

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
        self.finish()

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
