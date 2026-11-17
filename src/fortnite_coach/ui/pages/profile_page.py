from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from fortnite_coach.db.repositories.stats_repo import DashboardStats
from fortnite_coach.i18n.translator import tr
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.ui.widgets.empty_state import EmptyState
from fortnite_coach.ui.widgets.level_bar import LevelBar

TOP_N = 3


class ProfilePage(BasePage):
    page_key = "profile"
    name_saved = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.info_card = Card()
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        self.name_label = QLabel()
        name_row = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(64)
        self.save_btn = QPushButton(objectName="PrimaryButton")
        self.save_btn.clicked.connect(lambda: self.name_saved.emit(self.name_edit.text()))
        name_row.addWidget(self.name_edit, 1)
        name_row.addWidget(self.save_btn)
        self.device_label = QLabel()
        self.device_value = QLabel()
        form.addRow(self.name_label, name_row)
        form.addRow(self.device_label, self.device_value)
        self.info_card.body.addLayout(form)
        self.saved_hint = QLabel(objectName="StatHint")
        self.info_card.body.addWidget(self.saved_hint)
        self.content.addWidget(self.info_card)

        row = QHBoxLayout()
        row.setSpacing(16)
        self.strengths_card = Card()
        self.strengths_body = QLabel()
        self.strengths_body.setWordWrap(True)
        self.strengths_card.body.addWidget(self.strengths_body)
        self.weak_card = Card()
        self.weak_body = QLabel()
        self.weak_body.setWordWrap(True)
        self.weak_card.body.addWidget(self.weak_body)
        row.addWidget(self.strengths_card)
        row.addWidget(self.weak_card)
        self.content.addLayout(row)

        self.levels_card = Card()
        from PySide6.QtWidgets import QGridLayout

        lg = QGridLayout()
        lg.setHorizontalSpacing(18)
        self.overall_bar = LevelBar(big=True)
        lg.addWidget(self.overall_bar, 0, 0, 1, 4)
        self.level_bars: dict[str, tuple[QLabel, LevelBar]] = {}
        for i, key in enumerate(("building", "editing", "piece_control", "aim", "movement", "game_sense", "fight_execution")):
            name, bar = QLabel(objectName="StatLabel"), LevelBar()
            lg.addWidget(name, 1 + (i // 4) * 2, i % 4)
            lg.addWidget(bar, 2 + (i // 4) * 2, i % 4)
            self.level_bars[key] = (name, bar)
        self.levels_card.body.addLayout(lg)
        self.content.addWidget(self.levels_card)

        self.patterns_card = Card()
        self.patterns_empty = EmptyState("profile")
        self.patterns_list = QLabel()
        self.patterns_list.setWordWrap(True)
        self.patterns_card.body.addWidget(self.patterns_empty)
        self.patterns_card.body.addWidget(self.patterns_list)
        self.content.addWidget(self.patterns_card)
        self.levels = None
        self.repeated: list = []
        self.stats = DashboardStats()
        self._name = ""
        self.finish()

    def set_profile(self, display_name: str) -> None:
        self._name = display_name
        self.name_edit.setText(display_name)

    def show_saved(self) -> None:
        self.saved_hint.setText(tr("profile.saved"))

    def refresh(self, stats: DashboardStats, levels=None, repeated=None) -> None:
        self.stats = stats
        self.levels = levels
        self.repeated = repeated or []
        self.retranslate()

    def _skill_list(self, items: list[tuple[str, float]]) -> str:
        return "\n".join(f"{tr(f'skill.{k}')}  ·  {v:.0f}" for k, v in items)

    def retranslate(self) -> None:
        super().retranslate()
        self.info_card.set_title(tr("profile.player"))
        self.name_label.setText(tr("profile.name"))
        self.name_edit.setPlaceholderText(tr("profile.name_placeholder"))
        self.save_btn.setText(tr("common.save"))
        self.device_label.setText(tr("profile.input"))
        self.device_value.setText(tr("profile.keyboard_mouse"))
        rated = sorted(((k, v.average) for k, v in self.stats.skills.items()), key=lambda kv: kv[1])
        enough = len(rated) >= 2
        self.strengths_card.set_title(tr("profile.strengths"), tr("common.ai_estimate"))
        self.weak_card.set_title(tr("profile.weaknesses"), tr("common.ai_estimate"))
        nd = tr("profile.needs_two_skills")
        self.strengths_body.setText(self._skill_list(list(reversed(rated))[:TOP_N]) if enough else nd)
        self.weak_body.setText(self._skill_list(rated[:TOP_N]) if enough else nd)
        from fortnite_coach.ui.pages.history_page import code_label

        self.levels_card.set_title(tr("profile.levels"), tr("dash.levels_sub"))
        self.overall_bar.set_level(self.levels.overall if self.levels else None)
        for key, (name, bar) in self.level_bars.items():
            name.setText(tr(f"skill.{key}"))
            bar.set_level(self.levels.skills.get(key) if self.levels else None)
        self.patterns_card.set_title(tr("profile.patterns"), tr("profile.patterns_sub"))
        self.patterns_empty.set_text(tr("common.not_enough_data"), tr("profile.patterns_empty"))
        lines = [tr("profile.repeated_row", name=code_label(r.code, False), skill=tr(f"skill.{r.skill}"),
                    n=r.sessions, total=r.total) for r in self.repeated]
        self.patterns_list.setText("\n".join(lines))
        self.patterns_list.setVisible(bool(lines))
        self.patterns_empty.setVisible(not lines)
