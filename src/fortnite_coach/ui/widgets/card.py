from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class Card(QFrame):
    """Rounded panel with optional title/subtitle and a body layout."""

    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)
        self.header = QHBoxLayout()
        self.header.setSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title_label = QLabel(title, objectName="CardTitle")
        self.subtitle_label = QLabel(subtitle, objectName="CardSubtitle")
        self.subtitle_label.setWordWrap(True)
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)
        self.header.addLayout(titles, 1)
        outer.addLayout(self.header)
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        outer.addLayout(self.body, 1)
        self.set_title(title, subtitle)

    def set_title(self, title: str, subtitle: str = "") -> None:
        self.title_label.setText(title)
        self.title_label.setVisible(bool(title))
        self.subtitle_label.setText(subtitle)
        self.subtitle_label.setVisible(bool(subtitle))
