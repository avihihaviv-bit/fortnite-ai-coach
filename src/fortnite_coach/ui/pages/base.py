from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from fortnite_coach.i18n.translator import tr


class BasePage(QWidget):
    """Scrollable page with a title header. Subclasses implement ``retranslate``."""

    page_key: str = ""  # nav key, e.g. "dashboard"

    def __init__(self, parent: QWidget | None = None, *, dev_phase: int | None = None):
        super().__init__(parent)
        self.dev_phase = dev_phase  # set while the page is not functional yet
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(scroll)
        inner = QWidget()
        scroll.setWidget(inner)
        self.content = QVBoxLayout(inner)
        self.content.setContentsMargins(32, 28, 32, 28)
        self.content.setSpacing(18)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.title_label = QLabel(objectName="PageTitle")
        self.subtitle_label = QLabel(objectName="PageSubtitle")
        self.subtitle_label.setWordWrap(True)
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)
        header.addLayout(titles, 1)
        self.dev_badge = QLabel(objectName="DevBadge")
        self.dev_badge.setVisible(dev_phase is not None)
        header.addWidget(self.dev_badge, 0, Qt.AlignmentFlag.AlignTop)
        self.content.addLayout(header)

    def finish(self) -> None:
        """Call at the end of subclass __init__."""
        self.content.addStretch(1)
        self.retranslate()

    def retranslate(self) -> None:
        self.title_label.setText(tr(f"nav.{self.page_key}"))
        self.subtitle_label.setText(tr(f"page.{self.page_key}.subtitle"))
        if self.dev_phase is not None:
            self.dev_badge.setText(tr("common.in_development", phase=self.dev_phase))
            self.dev_badge.setToolTip(tr("common.in_development_tip"))
