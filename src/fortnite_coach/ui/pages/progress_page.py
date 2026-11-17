"""Progress: ratings over time, XP, weekly/monthly table, repeated vs resolved mistakes,
personal records and a side-by-side comparison of two sessions. Real data only."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QWidget,
)

from fortnite_coach.coaching.prompt_builder import fmt_ts  # noqa: F401
from fortnite_coach.core.skills import ALL_SKILLS
from fortnite_coach.db.repositories import progress_repo
from fortnite_coach.i18n.translator import tr
from fortnite_coach.ui.context import AppContext
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.ui.widgets.chart import SERIES_GREEN, SERIES_PURPLE, LineChart
from fortnite_coach.ui.widgets.empty_state import EmptyState


def _fmt(v) -> str:
    return "—" if v is None else (f"{v:g}" if isinstance(v, float) else str(v))


class ProgressPage(BasePage):
    page_key = "progress"

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.points: list[progress_repo.SessionPoint] = []

        # ---- filter row (one row above the charts) ----
        filters = QHBoxLayout()
        self.skill_label, self.period_label = QLabel(), QLabel()
        self.skill_combo = QComboBox()
        self.skill_combo.addItem("", "overall")
        for s in ALL_SKILLS:
            self.skill_combo.addItem("", s.value)
        self.skill_combo.currentIndexChanged.connect(lambda _i: self._render_charts())
        self.period_combo = QComboBox()
        self.period_combo.addItem("", "week")
        self.period_combo.addItem("", "month")
        self.period_combo.currentIndexChanged.connect(lambda _i: self._render_table())
        for w in (self.skill_label, self.skill_combo, self.period_label, self.period_combo):
            filters.addWidget(w)
        filters.addStretch(1)
        self.content.addLayout(filters)

        self.empty_card = Card()
        self.empty = EmptyState("progress")
        self.empty_card.body.addWidget(self.empty)
        self.content.addWidget(self.empty_card)

        charts = QHBoxLayout()
        charts.setSpacing(16)
        self.score_card = Card()
        self.score_chart = LineChart(SERIES_PURPLE, (0, 100))
        self.score_note = QLabel(objectName="StatHint")
        self.score_note.setWordWrap(True)
        self.score_card.body.addWidget(self.score_chart)
        self.score_card.body.addWidget(self.score_note)
        self.xp_card = Card()
        self.xp_chart = LineChart(SERIES_GREEN, None)
        self.xp_card.body.addWidget(self.xp_chart)
        charts.addWidget(self.score_card, 1)
        charts.addWidget(self.xp_card, 1)
        self.charts_box = QWidget()
        self.charts_box.setLayout(charts)
        self.content.addWidget(self.charts_box)

        self.table_card = Card()
        self.table = QTableWidget(0, 7)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(180)
        self.table_card.body.addWidget(self.table)
        self.content.addWidget(self.table_card)

        row = QHBoxLayout()
        row.setSpacing(16)
        self.mistakes_card = Card()
        self.mistakes_label = QLabel()
        self.mistakes_label.setWordWrap(True)
        self.mistakes_card.body.addWidget(self.mistakes_label)
        self.records_card = Card()
        self.records_label = QLabel()
        self.records_label.setWordWrap(True)
        self.records_card.body.addWidget(self.records_label)
        row.addWidget(self.mistakes_card, 1)
        row.addWidget(self.records_card, 1)
        self.lists_box = QWidget()
        self.lists_box.setLayout(row)
        self.content.addWidget(self.lists_box)

        self.compare_card = Card()
        cform = QFormLayout()
        self.older_label, self.newer_label = QLabel(), QLabel()
        self.older_combo, self.newer_combo = QComboBox(), QComboBox()
        self.older_combo.currentIndexChanged.connect(lambda _i: self._render_compare())
        self.newer_combo.currentIndexChanged.connect(lambda _i: self._render_compare())
        cform.addRow(self.older_label, self.older_combo)
        cform.addRow(self.newer_label, self.newer_combo)
        self.compare_card.body.addLayout(cform)
        self.compare_result = QLabel()
        self.compare_result.setWordWrap(True)
        self.compare_card.body.addWidget(self.compare_result)
        self.content.addWidget(self.compare_card)
        self.finish()

    # ------------------------------------------------------------------ data
    def reload(self) -> None:
        self.points = progress_repo.timeline(self.ctx.db)
        self._render()

    def _render(self) -> None:
        has = bool(self.points)
        self.empty_card.setVisible(not has)
        for w in (self.charts_box, self.table_card, self.lists_box):
            w.setVisible(has)
        self.compare_card.setVisible(len(self.points) >= 2)
        if not has:
            return
        self._render_charts()
        self._render_table()
        self._render_lists()
        self._fill_compare_combos()

    def _render_charts(self) -> None:
        key = self.skill_combo.currentData()
        name = tr("dash.overall_rating") if key == "overall" else tr(f"skill.{key}")
        pts = []
        for p in self.points:
            v = p.overall if key == "overall" else p.scores.get(key)
            if v is not None:
                pts.append((p.at, v, tr("progress.tip_score", name=name, value=f"{v:.0f}", date=f"{p.at:%Y-%m-%d}",
                                       mode=tr(f"mode.{p.game_mode}"))))
        self.score_card.set_title(tr("progress.score_title", name=name), tr("common.ai_estimate"))
        self.score_chart.set_points(pts)
        self.score_note.setText(tr("progress.need_points") if len(pts) < 2 else "")
        cum, xp_pts = 0, []
        for p in self.points:
            cum += p.xp
            xp_pts.append((p.at, float(cum), tr("progress.tip_xp", total=cum, gained=p.xp, date=f"{p.at:%Y-%m-%d}")))
        self.xp_card.set_title(tr("progress.xp_title"), tr("progress.xp_sub"))
        self.xp_chart.set_points(xp_pts)

    def _render_table(self) -> None:
        monthly = self.period_combo.currentData() == "month"
        rows = list(reversed(progress_repo.periods(self.ctx.db, monthly=monthly)))
        self.table_card.set_title(tr("progress.table_month" if monthly else "progress.table_week"), tr("common.measured"))
        heads = ["progress.col.period", "progress.col.sessions", "progress.col.minutes", "progress.col.mpm",
                 "progress.col.xp", "progress.col.training", "progress.col.training_min"]
        self.table.setHorizontalHeaderLabels([tr(h) for h in heads])
        self.table.setRowCount(len(rows))
        for r, p in enumerate(rows):
            for c, v in enumerate((p.key, p.sessions, round(p.analyzed_min, 1), p.mistakes_per_min, p.xp, p.completions,
                                   p.training_min)):
                self.table.setItem(r, c, QTableWidgetItem(_fmt(v)))

    def _render_lists(self) -> None:
        from fortnite_coach.ui.pages.history_page import code_label

        st = progress_repo.mistake_statuses(self.ctx.db)
        groups = {"repeated": [], "active": [], "resolved": []}
        for m in st:
            groups[m.status].append(tr("progress.mistake_row", name=code_label(m.code, False), skill=tr(f"skill.{m.skill}"),
                                       n=m.sessions, last=f"{m.last_seen:%Y-%m-%d}"))
        parts = []
        for k in ("repeated", "active", "resolved"):
            if groups[k]:
                parts.append(f"<b>{tr(f'progress.status.{k}')}</b><br>" + "<br>".join(groups[k]))
        self.mistakes_card.set_title(tr("progress.mistakes_title"),
                                     tr("progress.mistakes_sub", n=progress_repo.RESOLVED_AFTER))
        self.mistakes_label.setText("<br><br>".join(parts) or tr("progress.no_mistakes"))

        recs = progress_repo.personal_records(self.ctx.db)
        lines = []
        for r in recs:
            label = tr(f"progress.rec.{r.key}", skill=tr(f"skill.{r.detail}") if r.detail else "")
            when = f" · {r.at:%Y-%m-%d}" if r.at else ""
            lines.append(f"• {label}: <b>{r.value}</b>{when}")
        self.records_card.set_title(tr("progress.records_title"), tr("progress.records_sub"))
        self.records_label.setText("<br>".join(lines) or tr("common.not_enough_data"))

    def _fill_compare_combos(self) -> None:
        pair = progress_repo.default_pair(self.ctx.db)
        for combo in (self.older_combo, self.newer_combo):
            combo.blockSignals(True)
            combo.clear()
            for p in reversed(self.points):
                combo.addItem(f"{p.at:%Y-%m-%d %H:%M} · {tr(f'mode.{p.game_mode}')} · #{p.report_id}", p.report_id)
            combo.blockSignals(False)
        if pair:
            self.older_combo.setCurrentIndex(max(0, self.older_combo.findData(pair[0])))
            self.newer_combo.setCurrentIndex(max(0, self.newer_combo.findData(pair[1])))
        self._render_compare()

    def _render_compare(self) -> None:
        from fortnite_coach.ui.pages.history_page import code_label

        self.compare_card.set_title(tr("progress.compare_title"), tr("progress.compare_sub"))
        a, b = self.older_combo.currentData(), self.newer_combo.currentData()
        if a is None or b is None or a == b:
            self.compare_result.setText(tr("progress.compare_pick"))
            return
        c = progress_repo.compare(self.ctx.db, a, b)
        if c is None:
            return
        lines = []
        if c.older.game_mode != c.newer.game_mode:
            lines.append("⚠ " + tr("progress.compare_modes_differ"))
        lines.append(f"<b>{tr('progress.compare_scores')}</b> ({tr('common.ai_estimate')})")
        if c.score_changes:
            for skill, before, after in c.score_changes:
                arrow = "▲" if after > before else ("▼" if after < before else "＝")
                lines.append(f"{tr(f'skill.{skill}')}: {before:.0f} → {after:.0f} {arrow}")
        else:
            lines.append(tr("progress.compare_no_common"))
        lines.append(f"<b>{tr('progress.compare_counts')}</b> ({tr('common.measured')})")
        lines.append(tr("progress.compare_mpm", before=_fmt(c.older.mistakes_per_min), after=_fmt(c.newer.mistakes_per_min)))
        lines.append(tr("progress.compare_xp", before=c.older.xp, after=c.newer.xp))
        for key, codes in (("gone", c.gone), ("still", c.still), ("new", c.new)):
            if codes:
                lines.append(f"<b>{tr(f'progress.compare_{key}')}</b> " + ", ".join(code_label(x, False) for x in codes))
        self.compare_result.setText("<br>".join(lines))

    def retranslate(self) -> None:
        super().retranslate()
        self.skill_label.setText(tr("progress.skill"))
        self.period_label.setText(tr("progress.period"))
        self.skill_combo.setItemText(0, tr("dash.overall_rating"))
        for i in range(1, self.skill_combo.count()):
            self.skill_combo.setItemText(i, tr(f"skill.{self.skill_combo.itemData(i)}"))
        self.period_combo.setItemText(0, tr("progress.weekly"))
        self.period_combo.setItemText(1, tr("progress.monthly"))
        self.empty.set_text(tr("page.progress.empty_title"), tr("page.progress.empty_text"))
        self.older_label.setText(tr("progress.older"))
        self.newer_label.setText(tr("progress.newer"))
        if hasattr(self, "compare_result"):
            self.reload()
