"""Training Plan: personal exercises chosen from the player's own analyzed mistakes."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from fortnite_coach.coaching.exercises_catalog import BY_ID
from fortnite_coach.coaching.prompt_builder import fmt_ts
from fortnite_coach.coaching.training_plan import generate_plan
from fortnite_coach.db.repositories import plan_repo
from fortnite_coach.i18n.translator import get_translator, tr
from fortnite_coach.ui.context import AppContext
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.ui.widgets.empty_state import EmptyState


def reason_text(reason_json: str) -> str:
    from fortnite_coach.ui.pages.history_page import code_label

    try:
        r = json.loads(reason_json or "{}")
    except json.JSONDecodeError:
        return ""
    kind = r.get("kind")
    if kind == "warmup":
        return tr("plan.reason.warmup")
    parts = []
    if kind == "repeated":
        parts.append(tr("plan.reason.repeated", name=code_label(r["code"], False), n=r.get("sessions", 0)))
    elif kind == "latest":
        parts.append(tr("plan.reason.latest", name=code_label(r["code"], False)))
    elif kind == "weak_skill":
        score = r.get("score")
        parts.append(tr("plan.reason.weak", skill=tr(f"skill.{r.get('skill')}"),
                        score="?" if score is None else f"{score:.0f}"))
    if r.get("note"):
        ts = fmt_ts(r["t"]) if r.get("t") is not None else "--:--"
        parts.append(tr("plan.reason.note", t=ts, note=r["note"]))
    return "\n".join(parts)


class ExerciseCard(QFrame):
    def __init__(self, page: "TrainingPlanPage", ex, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ExerciseCard")
        self.page, self.ex = page, ex
        lang = get_translator().language
        t = BY_ID.get(ex.template_id or "")

        def txt(attr_t, fallback):
            return getattr(t, attr_t).get(lang) if t else fallback

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(6)
        head = QHBoxLayout()
        title = QLabel(f"{ex.order + 1}.  {txt('name', ex.name)}", objectName="FindingTitle")
        head.addWidget(title, 1)
        meta = QLabel(tr("plan.meta", category=tr(f"plan.cat.{ex.category}"), skill=tr(f"skill.{ex.skill}"),
                         difficulty=tr(f"difficulty.{ex.difficulty}"), minutes=ex.duration_min), objectName="StatHint")
        head.addWidget(meta)
        lay.addLayout(head)
        rows = [
            (tr("plan.goal"), txt("goal", ex.goal)), (tr("plan.how"), txt("instructions", ex.instructions)),
            (tr("plan.success"), txt("success", ex.success_criteria)), (tr("plan.level_up"), txt("level_up", ex.level_up_when)),
            (tr("plan.map"), txt("map_type", ex.map_type) + "  ·  " + tr("plan.map_note")),
        ]
        for label, text in rows:
            lbl = QLabel(f"<b>{label}</b>  {text}")
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
        why = QLabel(reason_text(ex.reason), objectName="ReasonBox")
        why.setWordWrap(True)
        lay.addWidget(why)
        from fortnite_coach.coaching.resources import links_html

        code = (ex.source_mistake_codes or [None])[0]
        self.guides = QLabel(f"<b>{tr('learn.guides')}</b>  " + links_html(code, ex.skill, tr("learn.videos"), tr("learn.articles")))
        self.guides.setOpenExternalLinks(True)
        self.guides.setWordWrap(True)
        lay.addWidget(self.guides)

        done_row = QHBoxLayout()
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 240)
        self.minutes.setValue(ex.duration_min)
        self.minutes.setSuffix(" " + tr("plan.min"))
        self.rating = QComboBox()
        self.rating.addItem(tr("plan.rating_none"), None)
        for i in range(1, 6):
            self.rating.addItem("★" * i, i)
        self.done_btn = QPushButton(tr("plan.mark_done"), objectName="PrimaryButton")
        self.done_btn.clicked.connect(self._done)
        self.undo_btn = QPushButton(tr("plan.undo"))
        self.undo_btn.clicked.connect(self._undo)
        n = len(ex.completions)
        self.count = QLabel(tr("plan.done_count", n=n) if n else tr("plan.not_done"), objectName="XpBadge" if n else "StatHint")
        self.undo_btn.setVisible(bool(n))
        for w in (QLabel(tr("plan.how_long")), self.minutes, QLabel(tr("plan.how_was_it")), self.rating, self.done_btn,
                  self.undo_btn):
            done_row.addWidget(w)
        done_row.addStretch(1)
        done_row.addWidget(self.count)
        lay.addLayout(done_row)

    def _done(self) -> None:
        plan_repo.complete_exercise(self.page.ctx.db, self.ex.id, self.minutes.value(), self.rating.currentData())
        self.page.reload()

    def _undo(self) -> None:
        plan_repo.undo_last_completion(self.page.ctx.db, self.ex.id)
        self.page.reload()


class TrainingPlanPage(BasePage):
    page_key = "training_plan"

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.summary_card = Card()
        srow = QHBoxLayout()
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.regen_btn = QPushButton()
        self.regen_btn.clicked.connect(self.regenerate)
        srow.addWidget(self.summary, 1)
        srow.addWidget(self.regen_btn)
        self.summary_card.body.addLayout(srow)
        self.effects = QLabel(objectName="StatHint")
        self.effects.setWordWrap(True)
        self.summary_card.body.addWidget(self.effects)
        self.content.addWidget(self.summary_card)

        self.empty_card = Card()
        self.empty = EmptyState("training_plan")
        self.empty_card.body.addWidget(self.empty)
        self.content.addWidget(self.empty_card)

        self.list_box = QWidget()
        self.list_layout = QGridLayout(self.list_box)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setVerticalSpacing(12)
        self.content.addWidget(self.list_box)
        self.cards: list[ExerciseCard] = []
        self.plan = None
        self.finish()

    def regenerate(self) -> None:
        generate_plan(self.ctx.db)
        self.reload()

    def reload(self) -> None:
        self.plan = plan_repo.active_plan(self.ctx.db)
        self._render()

    def _render(self) -> None:
        from fortnite_coach.ui.pages.history_page import HistoryPage  # noqa: F401  (code_label import side effects)

        while self.list_layout.count():
            w = self.list_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.cards = []
        plan = self.plan
        has = plan is not None and bool(plan.exercises)
        self.empty_card.setVisible(not has)
        self.list_box.setVisible(has)
        self.regen_btn.setText(tr("plan.regenerate"))
        self.regen_btn.setToolTip(tr("plan.regenerate_tip"))
        self.summary_card.set_title(tr("plan.title"), tr("plan.subtitle"))
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        totals = plan_repo.totals(self.ctx.db, since=week_ago)
        if has:
            done = sum(1 for e in plan.exercises if e.completions)
            minutes = sum(e.duration_min for e in plan.exercises)
            self.summary.setText(tr("plan.summary", date=f"{plan.created_at:%Y-%m-%d %H:%M}", n=len(plan.exercises),
                                    minutes=minutes, done=done, sessions=len(plan.based_on_report_ids or []),
                                    total=totals.completions, week=totals.this_week, mins=totals.minutes))
            for i, ex in enumerate(plan.exercises):
                card = ExerciseCard(self, ex)
                self.list_layout.addWidget(card, i, 0)
                self.cards.append(card)
        else:
            self.summary.setText(tr("plan.none"))
        eff = plan_repo.training_effects(self.ctx.db)
        lang = get_translator().language
        if eff:
            lines = [tr("plan.effect", name=BY_ID[e.template_id].name.get(lang) if e.template_id in BY_ID else e.template_id,
                        before=e.before_per_session, after=e.after_per_session, n=e.sessions_after) for e in eff]
            self.effects.setText(tr("plan.effects_title") + "\n" + "\n".join(lines))
        else:
            self.effects.setText(tr("plan.effects_none"))

    def retranslate(self) -> None:
        super().retranslate()
        self.empty.set_text(tr("page.training_plan.empty_title"), tr("page.training_plan.empty_text"))
        if hasattr(self, "list_layout"):
            self.reload()
