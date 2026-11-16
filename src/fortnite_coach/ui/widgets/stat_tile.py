from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from fortnite_coach.ui.theme import Colors


class StatTile(QFrame):
    """KPI tile. ``value=None`` renders the 'Not enough data' empty look."""

    def __init__(self, accent: str = Colors.BLUE, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(6)
        bar = QFrame(objectName="AccentBar")
        bar.setFixedSize(28, 4)
        bar.setStyleSheet(f"background: {accent};")
        self.label = QLabel(objectName="StatLabel")
        self.value = QLabel(objectName="StatValue")
        self.hint = QLabel(objectName="StatHint")
        self.hint.setWordWrap(True)
        for w in (bar, self.label, self.value, self.hint):
            lay.addWidget(w)
        lay.addStretch(1)

    def set_data(self, label: str, value: str | None, empty_text: str, hint: str = "") -> None:
        self.label.setText(label.upper() if label.isascii() else label)
        empty = value is None
        self.value.setText(empty_text if empty else value)
        self.value.setProperty("empty", "true" if empty else "false")
        self.value.style().unpolish(self.value)
        self.value.style().polish(self.value)
        self.hint.setText(hint)
        self.hint.setVisible(bool(hint))
