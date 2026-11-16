from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QWidget

from fortnite_coach.core.skills import ALL_SKILLS
from fortnite_coach.i18n.translator import tr
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.theme import Colors
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.ui.widgets.empty_state import EmptyState
from fortnite_coach.ui.widgets.stat_tile import StatTile


class DashboardPage(BasePage):
    page_key = "dashboard"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        tiles = QGridLayout()
        tiles.setSpacing(16)
        self.tile_rating = StatTile(Colors.PURPLE)
        self.tile_sessions = StatTile(Colors.BLUE)
        self.tile_strongest = StatTile(Colors.GREEN)
        self.tile_weakest = StatTile(Colors.AMBER)
        for i, t in enumerate((self.tile_rating, self.tile_sessions, self.tile_strongest, self.tile_weakest)):
            tiles.addWidget(t, 0, i)
        self.content.addLayout(tiles)

        row = QHBoxLayout()
        row.setSpacing(16)
        self.skills_card = Card()
        self.skill_rows: dict[str, tuple[QLabel, QLabel]] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)
        for i, skill in enumerate(ALL_SKILLS):
            name, value = QLabel(), QLabel(objectName="StatHint")
            grid.addWidget(name, i // 2, (i % 2) * 2)
            grid.addWidget(value, i // 2, (i % 2) * 2 + 1)
            self.skill_rows[skill.value] = (name, value)
        self.skills_card.body.addLayout(grid)
        row.addWidget(self.skills_card, 3)

        self.priorities_card = Card()
        self.priorities_empty = EmptyState("training_plan")
        self.priorities_card.body.addWidget(self.priorities_empty)
        row.addWidget(self.priorities_card, 2)
        self.content.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(16)
        self.weekly_card = Card()
        self.weekly_empty = EmptyState("progress")
        self.weekly_card.body.addWidget(self.weekly_empty)
        self.mistakes_card = Card()
        self.mistakes_empty = EmptyState("info")
        self.mistakes_card.body.addWidget(self.mistakes_empty)
        row2.addWidget(self.weekly_card, 1)
        row2.addWidget(self.mistakes_card, 1)
        self.content.addLayout(row2)

        self.recent_card = Card()
        self.recent_empty = EmptyState("history")
        self.recent_card.body.addWidget(self.recent_empty)
        self.content.addWidget(self.recent_card)
        self.finish()

    def retranslate(self) -> None:
        super().retranslate()
        nd = tr("common.not_enough_data")
        self.tile_rating.set_data(tr("dash.overall_rating"), None, nd, tr("common.ai_estimate"))
        self.tile_sessions.set_data(tr("dash.total_sessions"), "0", nd, tr("common.measured"))
        self.tile_strongest.set_data(tr("dash.strongest"), None, nd)
        self.tile_weakest.set_data(tr("dash.weakest"), None, nd)
        self.skills_card.set_title(tr("dash.skill_ratings"), tr("dash.skill_ratings_sub"))
        for key, (name, value) in self.skill_rows.items():
            name.setText(tr(f"skill.{key}"))
            value.setText(nd)
        self.priorities_card.set_title(tr("dash.priorities"))
        self.priorities_empty.set_text(tr("dash.empty_title"), tr("dash.priorities_empty"))
        self.weekly_card.set_title(tr("dash.weekly"))
        self.weekly_empty.set_text(nd, tr("dash.weekly_empty"))
        self.mistakes_card.set_title(tr("dash.repeated_mistakes"), tr("dash.improvements_sub"))
        self.mistakes_empty.set_text(nd, tr("dash.mistakes_empty"))
        self.recent_card.set_title(tr("dash.recent"))
        self.recent_empty.set_text(tr("dash.recent_empty_title"), tr("dash.recent_empty"))
