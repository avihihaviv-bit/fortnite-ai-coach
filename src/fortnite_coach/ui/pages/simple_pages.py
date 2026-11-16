"""Pages whose content is an honest empty state until their phase is built."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from fortnite_coach.i18n.translator import tr
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.ui.widgets.empty_state import EmptyState


class EmptyStatePage(BasePage):
    icon_name = "info"

    def __init__(self, parent: QWidget | None = None, *, dev_phase: int | None = None):
        super().__init__(parent, dev_phase=dev_phase)
        self.card = Card()
        self.empty = EmptyState(self.icon_name)
        self.card.body.addWidget(self.empty)
        self.content.addWidget(self.card)
        self.finish()

    def retranslate(self) -> None:
        super().retranslate()
        self.empty.set_text(tr(f"page.{self.page_key}.empty_title"), tr(f"page.{self.page_key}.empty_text"))


class GameplayAnalysisPage(EmptyStatePage):
    page_key = "gameplay"
    icon_name = "gameplay"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, dev_phase=4)


class TrainingSessionsPage(EmptyStatePage):
    page_key = "training_sessions"
    icon_name = "training_sessions"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, dev_phase=4)


class TrainingPlanPage(EmptyStatePage):
    page_key = "training_plan"
    icon_name = "training_plan"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, dev_phase=7)


class ProgressPage(EmptyStatePage):
    page_key = "progress"
    icon_name = "progress"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, dev_phase=8)


class HistoryPage(EmptyStatePage):
    page_key = "history"
    icon_name = "history"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, dev_phase=8)
