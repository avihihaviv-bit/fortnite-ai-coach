"""Ask the coach: write what you struggle with; get a personal answer, drills and what to search."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QWidget

from fortnite_coach.ai import usage_tracker
from fortnite_coach.ai.status import GeminiStatus
from fortnite_coach.coaching import ask_coach
from fortnite_coach.coaching.resources import links_html
from fortnite_coach.i18n.translator import tr
from fortnite_coach.ui.context import AppContext
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.workers.task import run_task

EXAMPLES = ("coach.example1", "coach.example2", "coach.example3", "coach.example4")


def answer_html(a: ask_coach.CoachAnswer) -> str:
    from fortnite_coach.i18n.translator import get_translator

    rtl = get_translator().is_rtl
    p_open = "<p dir='rtl' align='right'>" if rtl else "<p>"
    parts = [f"<p><b>{escape(tr('coach.you'))}</b> {escape(a.question)}</p>",
             f"<p>{escape(a.answer).replace(chr(10), '<br>')}</p>"]
    if a.key_points:
        parts.append(f"<p><b>{escape(tr('coach.remember'))}</b><br>" +
                     "<br>".join(f"• {escape(k)}" for k in a.key_points) + "</p>")
    for d in a.drills:
        parts.append(f"<p><b>🏋 {escape(d['name'])}</b> ({d['minutes']} {escape(tr('plan.min'))})<br>{escape(d['how'])}</p>")
    for q in a.search_queries:
        parts.append("<p>" + links_html(None, None, tr("learn.search"), q) + "</p>")
    return "".join(parts).replace("<p>", p_open)


class CoachPage(BasePage):
    page_key = "coach"

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.asking = False
        self.error = ""

        # ---- what I struggle with (saved, used in every analysis and by Live Coach) ----
        self.notes_card = Card()
        self.notes = QPlainTextEdit()
        self.notes.setFixedHeight(90)
        self.notes.setPlainText(ctx.settings().player_struggles)
        from PySide6.QtCore import QTimer

        self._notes_timer = QTimer(self)  # saved by itself a second after typing stops
        self._notes_timer.setSingleShot(True)
        self._notes_timer.setInterval(1000)
        self._notes_timer.timeout.connect(self.save_notes)
        self.notes.textChanged.connect(self._notes_timer.start)
        row = QHBoxLayout()
        self.notes_save = QPushButton(objectName="PrimaryButton")
        self.notes_save.clicked.connect(self.save_notes)
        self.notes_status = QLabel(objectName="StatHint")
        row.addWidget(self.notes_save)
        row.addWidget(self.notes_status, 1)
        self.notes_card.body.addWidget(self.notes)
        self.notes_card.body.addLayout(row)
        self.content.addWidget(self.notes_card)

        # ---- ask ----
        self.ask_card = Card()
        self.question = QPlainTextEdit()
        self.question.setFixedHeight(80)
        ex_row = QHBoxLayout()
        self.example_btns = []
        for key in EXAMPLES:
            b = QPushButton()
            b.clicked.connect(lambda _=False, k=key: self.question.setPlainText(tr(k)))
            ex_row.addWidget(b)
            self.example_btns.append((b, key))
        ex_row.addStretch(1)
        arow = QHBoxLayout()
        self.ask_btn = QPushButton(objectName="PrimaryButton")
        self.ask_btn.clicked.connect(self.ask)
        self.ask_status = QLabel(objectName="StatHint")
        self.ask_status.setWordWrap(True)
        arow.addWidget(self.ask_btn)
        arow.addWidget(self.ask_status, 1)
        self.answer = QLabel()
        self.answer.setWordWrap(True)
        self.answer.setTextFormat(Qt.TextFormat.RichText)
        self.answer.setOpenExternalLinks(True)
        self.answer.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        for w in (self.question,):
            self.ask_card.body.addWidget(w)
        self.ask_card.body.addLayout(ex_row)
        self.ask_card.body.addLayout(arow)
        self.ask_card.body.addWidget(self.answer)
        self.content.addWidget(self.ask_card)

        # ---- earlier answers ----
        self.history_card = Card()
        self.history = QLabel()
        self.history.setWordWrap(True)
        self.history.setTextFormat(Qt.TextFormat.RichText)
        self.history.setOpenExternalLinks(True)
        self.history_card.body.addWidget(self.history)
        self.content.addWidget(self.history_card)
        self.finish()

    def save_notes(self) -> None:
        s = self.ctx.settings()
        if s.player_struggles == self.notes.toPlainText().strip()[:600]:
            return
        s.player_struggles = self.notes.toPlainText().strip()[:600]
        self.ctx.save_settings(s)
        self.notes_status.setText(tr("coach.notes_saved"))

    def block_reason(self) -> str | None:
        status = self.ctx.gemini_status()
        if status is GeminiStatus.NOT_CONFIGURED:
            return "analysis.need_key"
        if status is not GeminiStatus.CONNECTED:
            return "analysis.need_test"
        return None

    def ask(self) -> None:
        if self.asking or self.block_reason():
            self.render()
            return
        q = self.question.toPlainText().strip()
        if not q:
            self.error = tr("coach.err_empty")
            self.render()
            return
        if self.notes.toPlainText().strip() != self.ctx.settings().player_struggles:
            self.save_notes()
        self.asking, self.error = True, ""
        self.render()
        db, settings, service = self.ctx.db, self.ctx.settings(), self.ctx.gemini_service()
        run_task(lambda: ask_coach.ask(db, settings, service, q), self._done, self._failed)

    def _done(self, ans) -> None:
        self.asking = False
        ask_coach.save_to_history(self.ctx.db, ans)
        self.answer.setText(answer_html(ans))
        self.question.clear()
        self.render()

    def _failed(self, err) -> None:
        from fortnite_coach.logging_setup import google_message

        self.asking = False
        key = getattr(err, "i18n_key", "error.generic")
        params = getattr(err, "params", {}) or {}
        self.error = tr("error.usage_limit_detail", **params) if key == "error.usage_limit" and params else tr(key)
        if key.startswith("gemini.") and str(err):
            self.error += "\n" + tr("gemini.details", text=google_message(str(err))[:300])
        self.render()

    def render(self) -> None:
        s = self.ctx.settings()
        self.notes_card.set_title(tr("coach.notes_title"), tr("coach.notes_sub"))
        self.notes.setPlaceholderText(tr("coach.notes_placeholder"))
        self.notes_save.setText(tr("common.save"))
        self.ask_card.set_title(tr("coach.ask_title"), tr("coach.ask_sub"))
        self.question.setPlaceholderText(tr("coach.question_placeholder"))
        for b, key in self.example_btns:
            b.setText(tr(key))
        reason = self.block_reason()
        self.ask_btn.setText(tr("coach.asking") if self.asking else tr("coach.ask"))
        self.ask_btn.setEnabled(not self.asking and reason is None)
        used = usage_tracker.requests_today(self.ctx.db)
        status = tr(reason) if reason else tr("coach.cost", used=used, limit=s.limits.max_requests_per_day)
        self.ask_status.setText(("⚠  " + self.error + "\n" if self.error else "") + status)
        self.history_card.set_title(tr("coach.history_title"), tr("coach.history_sub"))
        hist = ask_coach.load_history(self.ctx.db)
        self.history.setText("<hr>".join(answer_html(a) for a in hist[1:6]) or tr("coach.history_empty"))
        if not self.answer.text() and hist:
            self.answer.setText(answer_html(hist[0]))

    def retranslate(self) -> None:
        super().retranslate()
        if hasattr(self, "history"):
            self.render()
