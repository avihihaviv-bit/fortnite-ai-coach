"""History: every analyzed session, and the full report view for one of them."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QWidget

from fortnite_coach.coaching import taxonomy
from fortnite_coach.coaching.prompt_builder import fmt_ts
from fortnite_coach.db.repositories import report_repo, session_repo
from fortnite_coach.i18n.translator import get_translator, tr
from fortnite_coach.ui.context import AppContext
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.ui.widgets.empty_state import EmptyState
from fortnite_coach.ui.widgets.finding_card import FindingCard
from fortnite_coach.video.evidence import evidence_frames
from fortnite_coach.workers.task import run_task


def code_label(code: str, good: bool) -> str:
    lang = get_translator().language
    table = taxonomy.GOOD_PLAYS_BY_CODE if good else taxonomy.MISTAKES_BY_CODE
    item = table.get(code)
    return taxonomy.label(item, lang) if item else tr("report.other")


class HistoryPage(BasePage):
    page_key = "history"

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.current_report: int | None = None
        self.banner_text: str = ""

        self.list_card = Card()
        self.list = QListWidget()
        self.list.setMinimumHeight(160)
        self.list.itemActivated.connect(lambda it: self.show_report(it.data(Qt.ItemDataRole.UserRole)))
        self.list.itemClicked.connect(lambda it: self.show_report(it.data(Qt.ItemDataRole.UserRole)))
        self.empty = EmptyState("history")
        self.list_card.body.addWidget(self.list)
        self.list_card.body.addWidget(self.empty)
        self.content.addWidget(self.list_card)

        # report view (rebuilt per report)
        self.report_card = Card()
        self.report_holder = QWidget()
        self.report_layout = QGridLayout(self.report_holder)
        self.report_layout.setContentsMargins(0, 0, 0, 0)
        self.report_card.body.addWidget(self.report_holder)
        self.content.addWidget(self.report_card)
        self.report_card.hide()
        self._cards: list[tuple[FindingCard, float]] = []
        self.finish()
        self.refresh()

    # ------------------------------------------------------------ list
    def refresh(self) -> None:
        rows = report_repo.list_reports(self.ctx.db)
        self.list.clear()
        for r in rows:
            text = tr("history.row", date=f"{r.created_at:%Y-%m-%d %H:%M}", name=Path(r.video_path).name,
                      mode=tr(f"mode.{r.game_mode}"), analyzed=fmt_ts(r.analyzed_s), total=fmt_ts(r.total_s),
                      mistakes=r.mistakes, xp=r.xp)
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, r.report_id)
            self.list.addItem(item)
        self.list.setVisible(bool(rows))
        self.empty.setVisible(not rows)
        if self.current_report is not None and not any(r.report_id == self.current_report for r in rows):
            self.current_report = None
            self.report_card.hide()

    def show_report(self, report_id: int, banner: str = "") -> None:
        self.current_report = report_id
        self.banner_text = banner
        self._render_report()

    # ------------------------------------------------------------ report view
    def _clear_report(self) -> None:
        while self.report_layout.count():
            w = self.report_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._cards = []

    def _render_report(self) -> None:
        self._clear_report()
        d = report_repo.report_detail(self.ctx.db, self.current_report) if self.current_report else None
        if d is None:
            self.report_card.hide()
            return
        self.report_card.show()
        r = d.report
        self.report_card.set_title(tr("report.title", name=Path(d.video_path).name),
                                   tr("report.sub", mode=tr(f"mode.{d.game_mode}"), model=r.model,
                                      date=f"{r.created_at:%Y-%m-%d %H:%M}"))
        row = 0

        def add(w: QWidget, span: int = 2):
            nonlocal row
            self.report_layout.addWidget(w, row, 0, 1, span)
            row += 1

        if self.banner_text:
            add(QLabel(self.banner_text, objectName="Banner"))

        cov = r.coverage or []
        done = [c for c in cov if c.get("analyzed")]
        cov_lines = [tr("report.coverage", analyzed=fmt_ts(sum(c["end_s"] - c["start_s"] for c in done)),
                        total=fmt_ts(sum(c["end_s"] - c["start_s"] for c in cov)))]
        for c in cov:
            if not c.get("analyzed"):
                note = c.get("note") or "error.gemini"
                reason = {"over_limit": tr("report.over_limit"), "before_start": tr("report.before_start")}.get(note, None) \
                    or tr(note)
                cov_lines.append(tr("report.not_analyzed", start=fmt_ts(c["start_s"]), end=fmt_ts(c["end_s"]), reason=reason))
        if d.dropped:
            cov_lines.append(tr("report.dropped", n=d.dropped))
        cov_label = QLabel("\n".join(cov_lines))
        cov_label.setWordWrap(True)
        add(cov_label)

        if r.summary:
            summary = QLabel(r.summary)
            summary.setWordWrap(True)
            add(summary)

        scored = [s for s in d.scores if s.score is not None]
        scores_text = "   ·   ".join(f"{tr(f'skill.{s.skill}')} {s.score:.0f}" for s in scored) or tr("common.not_enough_data")
        scores = QLabel(f"<b>{tr('report.scores')}</b> ({tr('common.ai_estimate')})<br>{scores_text}")
        scores.setWordWrap(True)
        add(scores)

        xp_total = sum(g.amount for g in d.good_plays)
        add(QLabel(f"<b>{tr('report.good_plays', n=len(d.good_plays), xp=xp_total)}</b>"))
        for g in d.good_plays:
            card = FindingCard("good", f"{tr(f'skill.{g.skill}')} · {code_label(g.code, True)}", g.timestamp_s, [
                (tr("report.what"), g.description), (tr("report.evidence"), g.evidence),
                (tr("report.difficulty"), tr(f"difficulty.{g.difficulty}")),
            ], badge=f"+{g.amount} XP")
            add(card)
            self._cards.append((card, g.timestamp_s or 0))

        add(QLabel(f"<b>{tr('report.mistakes', n=len(d.mistakes))}</b>"))
        if not d.mistakes:
            add(QLabel(tr("report.no_mistakes")))
        for m in d.mistakes:
            conf = f"{m.confidence * 100:.0f}%" if m.confidence is not None else "?"
            card = FindingCard("mistake", f"{tr(f'skill.{m.skill}')} · {code_label(m.code, False)}", m.timestamp_s, [
                (tr("report.what"), m.what_happened), (tr("report.better"), m.better_option), (tr("report.why"), m.why),
                (tr("report.drill"), m.how_to_practice), (tr("report.evidence"), m.evidence),
                (tr("report.confidence"), conf),
            ], badge=tr(f"severity.{m.severity}"))
            add(card)
            self._cards.append((card, m.timestamp_s or 0))

        if d.not_determinable:
            nd = QLabel(f"<b>{tr('report.not_determinable')}</b><br>" + "<br>".join(f"• {x}" for x in d.not_determinable))
            nd.setWordWrap(True)
            add(nd)

        btns = QHBoxLayout()
        holder = QWidget()
        holder.setLayout(btns)
        open_btn = QPushButton(tr("video.open_player"))
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(d.video_path)))
        del_btn = QPushButton(tr("history.delete"), objectName="DangerButton")
        del_btn.clicked.connect(lambda: self._delete(r.session_id))
        btns.addWidget(open_btn)
        btns.addWidget(del_btn)
        btns.addStretch(1)
        add(holder)
        self.delete_btn = del_btn

        # evidence frames in the background (OpenCV seek per timestamp)
        stamps = sorted({t for _, t in self._cards})
        video, fp, frames_root = d.video_path, d.fingerprint, self.ctx.paths.frames_dir
        rid = self.current_report
        run_task(lambda: evidence_frames(video, fp, stamps, frames_root),
                 lambda res: self._set_frames(rid, res), lambda _e: None)

    def _set_frames(self, report_id: int, frames: dict) -> None:
        if report_id != self.current_report:
            return
        for card, t in self._cards:
            try:
                card.set_frame(frames.get(t))
            except RuntimeError:  # card deleted meanwhile
                pass

    def confirm(self, title: str, text: str) -> bool:
        return QMessageBox.question(self, title, text) == QMessageBox.StandardButton.Yes

    def _delete(self, session_id: int) -> None:
        if not self.confirm(tr("history.delete"), tr("history.delete_confirm")):
            return
        session_repo.delete_session(self.ctx.db, session_id)
        self.current_report = None
        self.report_card.hide()
        self.ctx.data_changed()

    def retranslate(self) -> None:
        super().retranslate()
        self.list_card.set_title(tr("history.list"), tr("history.list_sub"))
        self.empty.set_text(tr("page.history.empty_title"), tr("page.history.empty_text"))
        if hasattr(self, "list"):
            self.refresh()
            if self.current_report is not None:
                self._render_report()
