from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QWidget

from fortnite_coach.coaching import taxonomy
from fortnite_coach.core.skills import Skill
from fortnite_coach.db.repositories.stats_repo import DashboardStats
from fortnite_coach.i18n.translator import get_translator, tr
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.theme import Colors
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.ui.widgets.empty_state import EmptyState
from fortnite_coach.ui.widgets.finding_card import FindingCard
from fortnite_coach.ui.widgets.level_bar import LevelBar
from fortnite_coach.ui.widgets.stat_tile import StatTile


class SkillPage(BasePage):
    """One page per focus skill: what is evaluated, mistakes tracked, current score, findings."""

    def __init__(self, skill: Skill, parent: QWidget | None = None):
        self.skill = skill
        self.page_key = skill.value
        super().__init__(parent)
        row = QHBoxLayout()
        row.setSpacing(16)
        self.score_tile = StatTile(Colors.PURPLE)
        self.sessions_tile = StatTile(Colors.PURPLE_LIGHT)
        self.level_card = Card()
        self.level_bar = LevelBar()
        self.level_card.body.addWidget(self.level_bar)
        self.level_card.setMinimumWidth(320)
        row.addWidget(self.level_card)
        row.addWidget(self.score_tile)
        row.addWidget(self.sessions_tile)
        row.addStretch(1)
        self.content.addLayout(row)

        cols = QHBoxLayout()
        cols.setSpacing(16)
        self.rubric_card = Card()
        self.criteria = taxonomy.criteria_for(skill)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        self.criteria_labels: list[QLabel] = []
        for i, _c in enumerate(self.criteria):
            lbl = QLabel()
            lbl.setWordWrap(True)
            grid.addWidget(lbl, i // 2, i % 2)
            self.criteria_labels.append(lbl)
        self.rubric_card.body.addLayout(grid)
        self.note = QLabel(objectName="StatHint")
        self.note.setWordWrap(True)
        self.rubric_card.body.addWidget(self.note)
        cols.addWidget(self.rubric_card, 3)

        self.mistakes_card = Card()
        self.mistake_types = taxonomy.mistakes_for(skill)
        self.mistake_labels: list[QLabel] = []
        for _m in self.mistake_types:
            lbl = QLabel(objectName="StatHint")
            lbl.setWordWrap(True)
            self.mistakes_card.body.addWidget(lbl)
            self.mistake_labels.append(lbl)
        cols.addWidget(self.mistakes_card, 2)
        self.content.addLayout(cols)

        self.findings_card = Card()
        self.findings_empty = EmptyState(skill.value)
        self.findings_card.body.addWidget(self.findings_empty)
        self.findings_box = QWidget()
        from PySide6.QtWidgets import QVBoxLayout

        self.findings_layout = QVBoxLayout(self.findings_box)
        self.findings_layout.setContentsMargins(0, 0, 0, 0)
        self.findings_layout.setSpacing(8)
        self.findings_card.body.addWidget(self.findings_box)
        self.content.addWidget(self.findings_card)
        self.stats = DashboardStats()
        self.level = None
        self.findings: list = []
        self.finish()

    def refresh(self, stats: DashboardStats, level=None, findings=None) -> None:
        self.stats = stats
        self.level = level
        self.findings = findings or []
        self.retranslate()

    def _render_findings(self) -> None:
        from fortnite_coach.ui.pages.history_page import code_label

        while self.findings_layout.count():
            w = self.findings_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        for f in self.findings:
            good = f.kind == "good"
            card = FindingCard(f.kind, code_label(f.code, good), f.timestamp_s,
                               [(tr("report.what"), f.text),
                                (tr("report.evidence") if good else tr("report.better"), f.detail)],
                               badge=f"+{f.xp} XP" if good else "")
            card.frame.hide()
            self.findings_layout.addWidget(card)
        self.findings_box.setVisible(bool(self.findings))
        self.findings_empty.setVisible(not self.findings)

    def retranslate(self) -> None:
        super().retranslate()
        lang = get_translator().language
        nd = tr("common.not_enough_data")
        stat = self.stats.skills.get(self.skill.value)
        self.score_tile.set_data(
            tr("skillpage.score"), None if stat is None else f"{stat.average:.0f}", nd, tr("common.ai_estimate")
        )
        self.sessions_tile.set_data(
            tr("skillpage.sessions"), str(0 if stat is None else stat.samples), nd, tr("common.measured")
        )
        self.rubric_card.set_title(tr("skillpage.rubric"), tr("skillpage.rubric_sub"))
        for lbl, c in zip(self.criteria_labels, self.criteria):
            lbl.setText("•  " + taxonomy.label(c, lang))
        note_key = f"rubric.{self.skill.value}.note"
        note = tr(note_key)
        self.note.setText(note if note != note_key else "")
        self.note.setVisible(note != note_key)
        self.mistakes_card.set_title(tr("skillpage.tracked_mistakes"), tr("skillpage.tracked_mistakes_sub"))
        for lbl, m in zip(self.mistake_labels, self.mistake_types):
            lbl.setText("–  " + taxonomy.label(m, lang))
        self.findings_card.set_title(tr("skillpage.findings"), tr("skillpage.findings_sub"))
        self.findings_empty.set_text(nd, tr("skillpage.findings_empty"))
        self.level_card.set_title(tr("skillpage.level"), tr("skillpage.level_sub"))
        self.level_bar.set_level(self.level)
        self._render_findings()
