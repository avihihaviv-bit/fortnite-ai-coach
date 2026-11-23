from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from fortnite_coach.ai.status import GeminiStatus
from fortnite_coach.i18n.translator import get_translator, tr
from fortnite_coach.ui import icons
from fortnite_coach.ui.theme import Colors
from fortnite_coach.ui.widgets.status_pill import StatusPill

# (section i18n key, [nav keys])
NAV_SECTIONS: list[tuple[str, list[str]]] = [
    ("nav.section.overview", ["dashboard", "profile"]),
    ("nav.section.analyze", ["gameplay", "training_sessions", "clips"]),
    ("nav.section.skills", ["building", "editing", "piece_control", "aim", "movement", "mechanics", "game_sense"]),
    ("nav.section.improve", ["coach", "training_plan", "progress", "history"]),
    ("nav.section.app", ["help", "settings"]),
]
NAV_KEYS: list[str] = [k for _, keys in NAV_SECTIONS for k in keys]


class Sidebar(QFrame):
    navigated = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(236)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 20, 12, 16)
        lay.setSpacing(2)

        accent = QLabel("AI COACH", objectName="SidebarLogoAccent")
        logo = QLabel("FORTNITE", objectName="SidebarLogo")
        lay.addWidget(accent)
        lay.addWidget(logo)
        lay.addSpacing(10)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        self.section_labels: list[tuple[QLabel, str]] = []
        for section_key, keys in NAV_SECTIONS:
            sl = QLabel(objectName="SidebarSection")
            self.section_labels.append((sl, section_key))
            lay.addWidget(sl)
            for key in keys:
                btn = QPushButton(objectName="NavButton")
                btn.setCheckable(True)
                btn.setIcon(icons.icon(key, Colors.TEXT_MUTED, Colors.PURPLE_LIGHT))
                btn.setIconSize(QSize(18, 18))
                btn.clicked.connect(lambda _=False, k=key: self.navigated.emit(k))
                self.group.addButton(btn)
                self.buttons[key] = btn
                lay.addWidget(btn)
        lay.addStretch(1)
        self.rec_pill = StatusPill()
        self.rec_pill.hide()
        lay.addWidget(self.rec_pill)
        lay.addSpacing(6)
        self.status = StatusPill()
        lay.addWidget(self.status)
        self._gemini = GeminiStatus.NOT_CONFIGURED
        self.retranslate()

    def set_current(self, key: str) -> None:
        self.buttons[key].setChecked(True)

    def set_recording(self, active: bool, elapsed_s: float, live: bool = False) -> None:
        self.rec_pill.setVisible(active or live)
        m, sec = divmod(int(elapsed_s), 60)
        if active:
            text = f"REC  {m:02d}:{sec:02d}" + ("  ·  LIVE" if live else "")
            self.rec_pill.set_state("error", text, tr("rec.recording"))
        elif live:
            self.rec_pill.set_state("ok", "LIVE COACH", tr("live.on"))

    def set_gemini_status(self, status: GeminiStatus) -> None:
        self._gemini = status
        self.status.set_state(status.pill_state, tr(status.i18n_key), tr("gemini.status_tip"))

    def retranslate(self) -> None:
        rtl = get_translator().is_rtl
        for label, key in self.section_labels:
            label.setText(tr(key))
        for key, btn in self.buttons.items():
            btn.setText("  " + tr(f"nav.{key}"))
            btn.setToolTip(tr(f"page.{key}.subtitle"))
            btn.setProperty("rtl", "true" if rtl else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.set_gemini_status(self._gemini)
