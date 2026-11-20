from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
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
        self.weekly_label = QLabel()
        self.weekly_label.setWordWrap(True)
        self.weekly_card.body.addWidget(self.weekly_empty)
        self.weekly_card.body.addWidget(self.weekly_label)
        self.mistakes_card = Card()
        self.mistakes_empty = EmptyState("info")
        self.mistakes_list = QLabel()
        self.mistakes_list.setWordWrap(True)
        self.mistakes_card.body.addWidget(self.mistakes_empty)
        self.mistakes_card.body.addWidget(self.mistakes_list)
        row2.addWidget(self.weekly_card, 1)
        row2.addWidget(self.mistakes_card, 1)
        self.content.addLayout(row2)

        self.search_card = Card()
        self.search_empty = EmptyState("spark")
        self.search_list = QLabel()
        self.search_list.setWordWrap(True)
        self.search_list.setOpenExternalLinks(True)
        self.search_list.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.search_card.body.addWidget(self.search_empty)
        self.search_card.body.addWidget(self.search_list)
        self.content.addWidget(self.search_card)
        self.struggles: list = []

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
        self.periods: list = []
        self.finish()

    def refresh(self, stats: DashboardStats, levels=None, recent=None, repeated=None, periods=None,
                struggles=None, queries=None) -> None:
        self.struggles = struggles or []
        self.queries = queries or {}
        self.periods = periods or []
        self.stats = stats
        self.levels = levels
        self.recent = recent or []
        self.repeated = repeated or []
        self.retranslate()

    def _render_search(self) -> None:
        from html import escape

        from fortnite_coach.coaching.resources import links_html
        from fortnite_coach.ui.pages.history_page import code_label

        self.search_card.set_title(tr("search.title"), tr("search.subtitle"))
        self.search_empty.set_text(tr("search.empty_title"), tr("search.empty_text"))
        items = []
        for i, sg in enumerate(self.struggles):
            name = code_label(sg.code, False) if sg.code != "OTHER" else (sg.example[:70] or tr("report.other"))
            seen = tr("dash.seen_in", n=sg.sessions) if sg.sessions > 1 else tr("search.seen_once")
            example = f"<br><i style='color:#9CA3AF'>{escape(sg.example[:160])}</i>" if sg.example else ""
            items.append(f"<b>{i + 1}. {escape(name)}</b> ({tr(f'skill.{sg.skill}')}) · {seen} · "
                         f"{tr(f'severity.{sg.severity}')}{example}<br>"
                         f"{links_html(sg.code if sg.code != 'OTHER' else None, sg.skill, tr('learn.search'), sg.query)}")
        self.search_list.setText("<br><br>".join(items))
        self.search_list.setVisible(bool(items))
        self.search_empty.setVisible(not items)

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
        from fortnite_coach.coaching.resources import links_html

        label = tr("learn.search")
        queries = getattr(self, "queries", {}) or {}
        prio = [f"<b>{i + 1}. {code_label(r.code, False)}</b> ({tr(f'skill.{r.skill}')}) · {tr('dash.seen_in', n=r.sessions)}"
                f"<br>{links_html(r.code, r.skill, label, queries.get(r.code))}"
                for i, r in enumerate(self.repeated[:3])]
        if not prio and self.struggles:  # after the first analysis: the biggest problems seen so far
            prio = [f"<b>{i + 1}. {code_label(g.code, False) if g.code != 'OTHER' else g.example[:60]}</b> "
                    f"({tr(f'skill.{g.skill}')}) · {tr(f'severity.{g.severity}')}"
                    f"<br>{links_html(g.code if g.code != 'OTHER' else None, g.skill, label, g.query)}"
                    for i, g in enumerate(self.struggles[:3])]
        if not prio and st.weakest:
            prio = [f"<b>1. {tr(f'skill.{st.weakest}')}</b> · {tr('dash.lowest_score')}"
                    f"<br>{links_html(None, st.weakest, label)}"]
        self.priorities_list.setOpenExternalLinks(True)
        self._render_search()
        self.priorities_list.setText("<br>".join(prio))
        self.priorities_list.setVisible(bool(prio))
        self.priorities_empty.setVisible(not prio)
        from datetime import datetime, timedelta, timezone

        from fortnite_coach.db.repositories.progress_repo import _week_key

        now = datetime.now(timezone.utc)
        this_k, last_k = _week_key(now), _week_key(now - timedelta(days=7))
        by = {p.key: p for p in self.periods}
        self.weekly_card.set_title(tr("dash.weekly"), tr("common.measured"))
        self.weekly_empty.set_text(nd, tr("dash.weekly_empty"))
        if this_k in by or last_k in by:
            def col(p):
                return (p.sessions, "—" if p.mistakes_per_min is None else f"{p.mistakes_per_min:g}", p.xp, p.completions) \
                    if p else (0, "—", 0, 0)
            a, b = col(by.get(this_k)), col(by.get(last_k))
            rows = [tr("dash.week_head")]
            for i, key in enumerate(("dash.week_sessions", "dash.week_mpm", "dash.week_xp", "dash.week_training")):
                rows.append(f"{tr(key)}:  <b>{a[i]}</b>  ·  {b[i]}")
            self.weekly_label.setText("<br>".join(rows))
            self.weekly_label.setVisible(True)
            self.weekly_empty.setVisible(False)
        else:
            self.weekly_label.setVisible(False)
            self.weekly_empty.setVisible(True)
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
