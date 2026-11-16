from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from fortnite_coach.core.skills import Skill
from fortnite_coach.i18n.translator import tr
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.theme import Colors
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.ui.widgets.empty_state import EmptyState
from fortnite_coach.ui.widgets.stat_tile import StatTile

# Number of rubric criteria listed per skill page (keys rubric.<skill>.<n> in the catalogs).
RUBRIC_SIZES = {
    Skill.BUILDING: 6,
    Skill.EDITING: 6,
    Skill.PIECE_CONTROL: 6,
    Skill.AIM: 5,
    Skill.GAME_SENSE: 7,
}
ICON_FOR = {
    Skill.BUILDING: "building",
    Skill.EDITING: "editing",
    Skill.PIECE_CONTROL: "piece_control",
    Skill.AIM: "aim",
    Skill.GAME_SENSE: "game_sense",
}


class SkillPage(BasePage):
    """One page per focus skill: what is evaluated, current score, findings."""

    def __init__(self, skill: Skill, parent: QWidget | None = None):
        self.skill = skill
        self.page_key = skill.value
        super().__init__(parent)
        row = QHBoxLayout()
        row.setSpacing(16)
        self.score_tile = StatTile(Colors.PURPLE)
        self.sessions_tile = StatTile(Colors.BLUE)
        row.addWidget(self.score_tile)
        row.addWidget(self.sessions_tile)
        row.addStretch(1)
        self.content.addLayout(row)

        self.rubric_card = Card()
        self.rubric_labels = []
        for _ in range(RUBRIC_SIZES[skill]):
            lbl = QLabel()
            lbl.setWordWrap(True)
            self.rubric_card.body.addWidget(lbl)
            self.rubric_labels.append(lbl)
        self.note = QLabel(objectName="StatHint")
        self.note.setWordWrap(True)
        self.rubric_card.body.addWidget(self.note)
        self.content.addWidget(self.rubric_card)

        self.findings_card = Card()
        self.findings_empty = EmptyState(ICON_FOR[skill])
        self.findings_card.body.addWidget(self.findings_empty)
        self.content.addWidget(self.findings_card)
        self.finish()

    def retranslate(self) -> None:
        super().retranslate()
        nd = tr("common.not_enough_data")
        self.score_tile.set_data(tr("skillpage.score"), None, nd, tr("common.ai_estimate"))
        self.sessions_tile.set_data(tr("skillpage.sessions"), "0", nd, tr("common.measured"))
        self.rubric_card.set_title(tr("skillpage.rubric"), tr("skillpage.rubric_sub"))
        for i, lbl in enumerate(self.rubric_labels, start=1):
            lbl.setText("•  " + tr(f"rubric.{self.skill.value}.{i}"))
        note_key = f"rubric.{self.skill.value}.note"
        note = tr(note_key)
        self.note.setText(note if note != note_key else "")
        self.note.setVisible(note != note_key)
        self.findings_card.set_title(tr("skillpage.findings"))
        self.findings_empty.set_text(nd, tr("skillpage.findings_empty"))
