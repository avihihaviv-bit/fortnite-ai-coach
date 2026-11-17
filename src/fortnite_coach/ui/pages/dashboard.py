from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QWidget

from fortnite_coach.core.skills import ALL_SKILLS
from fortnite_coach.db.repositories.stats_repo import DashboardStats
from fortnite_coach.i18n.translator import tr
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.theme import Colors
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.ui.widgets.empty_state import EmptyState
from fortnite_coach.ui.widgets.level_bar import LevelBar
from fortnite_coach.ui.widgets.stat_tile import StatTile

SKILL_LEVEL_ORDER = ("building", "editing", "piece_control", "aim", "movement", "game_sense", "fight_execution")


class DashboardPage(BasePage):
    page_key = "dashboard"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        # ---- levels (XP only from good plays seen in analyzed videos) ----
        self.level_card = Card()
        lrow = QHBoxLayout()
        lrow.setSpacing(28)
        self.overall_level = LevelBar(big=True)
        lrow.addWidget(self.overall_level, 2)
        sgrid = QGridLayout()
        sgrid.setHorizontalSpacing(18)
        sgrid.setVerticalSpacing(6)
        self.skill_levels: dict[str, tuple[QLabel, LevelBar]] = {}
        for i, key in enumerate(SKILL_LEVEL_ORDER):
            name, bar = QLabel(objectName="StatLabel"), LevelBar()
            sgrid.addWidget(name, (i // 4) * 2, i % 4)
            sgrid.addWidget(bar, (i // 4) * 2 + 1, i % 4)
            self.skill_levels[key] = (name, bar)
        lrow.addLayout(sgrid, 5)
        self.level_card.body.addLayout(lrow)
        self.content.addWidget(self.level_card)

        tiles = QGridLayout()
        tiles.setSpacing(16)
        self.tile_rating = StatTile(Colors.PURPLE)
        self.tile_sessions = StatTile(Colors.PURPLE_LIGHT)
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
        self.priorities_list = QLabel()
        self.priorities_list.setWordWrap(True)
        self.priorities_card.body.addWidget(self.priorities_empty)
        self.priorities_card.body.addWidget(self.priorities_list)
        row.addWidget(self.priorities_card, 2)
        self.content.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(16)
        self.weekly_card = Card()
        self.weekly_empty = EmptyState("progress")
        self.weekly_card.body.addWidget(self.weekly_empty)
        self.mistakes_card = Card()
        self.mistakes_empty = EmptyState("info")
        self.mistakes_list = QLabel()
        self.mistakes_list.setWordWrap(True)
        self.mistakes_card.body.addWidget(self.mistakes_empty)
        self.mistakes_card.body.addWidget(self.mistakes_list)
        row2.addWidget(self.weekly_card, 1)
        row2.addWidget(self.mistakes_card, 1)
        self.content.addLayout(row2)

        self.recent_card = Card()
        self.recent_empty = EmptyState("history")
        self.recent_list = QLabel()
        self.recent_list.setWordWrap(True)
        self.recent_card.body.addWidget(self.recent_empty)
        self.recent_card.body.addWidget(self.recent_list)
        self.content.addWidget(self.recent_card)
        self.stats = DashboardStats()
        self.levels = None
        self.recent: list = []
        self.repeated: list = []
        self.finish()

    def refresh(self, stats: DashboardStats, levels=None, recent=None, repeated=None) -> None:
        self.stats = stats
        self.levels = levels
        self.recent = recent or []
        self.repeated = repeated or []
        self.retranslate()

    def retranslate(self) -> None:
        super().retranslate()
        nd = tr("common.not_enough_data")
        st = self.stats
        overall = None if st.overall is None else f"{st.overall:.0f}"
        self.tile_rating.set_data(tr("dash.overall_rating"), overall, nd, tr("common.ai_estimate"))
        self.tile_sessions.set_data(tr("dash.total_sessions"), str(st.analyzed_sessions), nd, tr("common.measured"))
        self.tile_strongest.set_data(tr("dash.strongest"), st.strongest and tr(f"skill.{st.strongest}"), nd)
        self.tile_weakest.set_data(tr("dash.weakest"), st.weakest and tr(f"skill.{st.weakest}"), nd)
        self.skills_card.set_title(tr("dash.skill_ratings"), tr("dash.skill_ratings_sub"))
        for key, (name, value) in self.skill_rows.items():
            name.setText(tr(f"skill.{key}"))
            stat = st.skills.get(key)
            value.setText(nd if stat is None else tr("dash.skill_value", score=f"{stat.average:.0f}", n=stat.samples))
        from fortnite_coach.ui.pages.history_page import code_label

        self.level_card.set_title(tr("dash.levels"), tr("dash.levels_sub"))
        self.overall_level.set_level(self.levels.overall if self.levels else None)
        for key, (name, bar) in self.skill_levels.items():
            name.setText(tr(f"skill.{key}"))
            bar.set_level(self.levels.skills.get(key) if self.levels else None)

        self.priorities_card.set_title(tr("dash.priorities"), tr("dash.priorities_sub"))
        self.priorities_empty.set_text(tr("dash.empty_title"), tr("dash.priorities_empty"))
        prio = [f"{i + 1}. {code_label(r.code, False)} ({tr(f'skill.{r.skill}')}) · {tr('dash.seen_in', n=r.sessions)}"
                for i, r in enumerate(self.repeated[:3])]
        if not prio and st.weakest:
            prio = [f"1. {tr(f'skill.{st.weakest}')} · {tr('dash.lowest_score')}"]
        self.priorities_list.setText("\n".join(prio))
        self.priorities_list.setVisible(bool(prio))
        self.priorities_empty.setVisible(not prio)
        self.weekly_card.set_title(tr("dash.weekly"))
        self.weekly_empty.set_text(nd, tr("dash.weekly_empty"))
        self.mistakes_card.set_title(tr("dash.repeated_mistakes"), tr("dash.improvements_sub"))
        self.mistakes_empty.set_text(nd, tr("dash.mistakes_empty"))
        rep = [f"• {code_label(r.code, False)} · {tr('dash.seen_in', n=r.sessions)}" for r in self.repeated[:6]]
        self.mistakes_list.setText("\n".join(rep))
        self.mistakes_list.setVisible(bool(rep))
        self.mistakes_empty.setVisible(not rep)
        self.recent_card.set_title(tr("dash.recent"))
        self.recent_empty.set_text(tr("dash.recent_empty_title"), tr("dash.recent_empty"))
        rec = [tr("dash.recent_row", date=f"{r.created_at:%Y-%m-%d}", name=Path(r.video_path).name,
                  mode=tr(f"mode.{r.game_mode}"), mistakes=r.mistakes, xp=r.xp) for r in self.recent]
        self.recent_list.setText("\n".join(rec))
        self.recent_list.setVisible(bool(rec))
        self.recent_empty.setVisible(not rec)
