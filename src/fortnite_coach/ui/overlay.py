"""Small always-on-top tip box in the top-left corner of the screen.

Click-through (mouse passes to the game), never takes focus, hides itself after a few seconds.
Works over Fortnite in Windowed Fullscreen / Borderless; exclusive Fullscreen hides any overlay.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class TipOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setObjectName("TipOverlay")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(objectName="TipOverlayText")
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(460)
        self.label.setStyleSheet(
            "QLabel#TipOverlayText { background: rgba(14,15,18,215); color: #F5F5F7; border-left: 4px solid #8B5CF6;"
            " border-radius: 8px; padding: 10px 14px; font-size: 17px; font-weight: 600; }")
        lay.addWidget(self.label)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self.monitor_index = 0

    def show_tip(self, text: str, seconds: int = 12, icon: str = "🎯") -> None:
        self.label.setText(f"{icon}  {text}" if icon else text)
        self.label.adjustSize()
        self.adjustSize()
        screens = QGuiApplication.screens()
        screen = screens[self.monitor_index] if 0 <= self.monitor_index < len(screens) else QGuiApplication.primaryScreen()
        if screen is not None:
            g = screen.geometry()
            self.move(g.left() + 24, g.top() + 24)
        self.show()
        self.raise_()
        self._hide_timer.start(max(1, seconds) * 1000)

    @property
    def text(self) -> str:
        return self.label.text()
