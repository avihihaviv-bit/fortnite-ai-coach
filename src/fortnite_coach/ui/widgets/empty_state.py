from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from fortnite_coach.ui import icons
from fortnite_coach.ui.theme import Colors


class EmptyState(QWidget):
    """Centered icon + message shown when there is no real data yet."""

    action_clicked = Signal()

    def __init__(self, icon_name: str = "info", parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 24, 16, 24)
        lay.setSpacing(8)
        self.icon = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.icon.setPixmap(icons.pixmap(icon_name, Colors.PURPLE, 36))
        self.title = QLabel(objectName="EmptyTitle", alignment=Qt.AlignmentFlag.AlignCenter)
        self.text = QLabel(objectName="EmptyText", alignment=Qt.AlignmentFlag.AlignCenter)
        self.text.setWordWrap(True)
        self.button = QPushButton(objectName="PrimaryButton")
        self.button.clicked.connect(self.action_clicked)
        self.button.hide()
        lay.addStretch(1)
        # Word-wrapped labels must be added WITHOUT a layout alignment flag,
        # otherwise Qt does not compute their wrapped height (text gets clipped).
        for w in (self.icon, self.title, self.text):
            lay.addWidget(w)
        lay.addSpacing(6)
        lay.addWidget(self.button, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch(1)

    def set_text(self, title: str, text: str, action: str | None = None) -> None:
        self.title.setText(title)
        self.text.setText(text)
        self.button.setVisible(bool(action))
        if action:
            self.button.setText(action)
