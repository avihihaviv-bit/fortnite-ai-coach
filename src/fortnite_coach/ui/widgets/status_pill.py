from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget


class StatusPill(QLabel):
    """Small colored status label. state: ok | warn | error | off."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("StatusPill")
        self.setWordWrap(True)
        self.set_state("off", "")

    def set_state(self, state: str, text: str, tooltip: str = "") -> None:
        self.setProperty("state", state)
        self.setText(f"●  {text}")
        self.setToolTip(tooltip)
        self.style().unpolish(self)
        self.style().polish(self)
