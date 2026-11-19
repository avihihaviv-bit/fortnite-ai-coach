"""Extra Settings cards: API usage, knowledge updates, about/privacy/self-test."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QMessageBox, QProgressBar, QPushButton, QTableWidget, QTableWidgetItem,
)

from fortnite_coach import __version__
from fortnite_coach.ai import request_cache, usage_tracker
from fortnite_coach.ai.status import GeminiStatus
from fortnite_coach.db.repositories import knowledge_repo
from fortnite_coach.i18n.translator import tr
from fortnite_coach.ui.context import AppContext
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.workers.task import run_task


def docs_path(name: str) -> Path:
    """Bundled copy in the EXE, or the repository docs folder when running from source."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) / "docs" / name if base else Path(__file__).resolve().parents[4] / "docs" / name


def _open(path: Path) -> None:
    if path.exists():
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def _wrap(label: QLabel) -> QLabel:
    label.setWordWrap(True)
    return label


class UsageCard(Card):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.limit_label = QLabel()
        self.limit_bar = QProgressBar(objectName="XpBar")
        self.limit_bar.setTextVisible(False)
        self.limit_bar.setFixedHeight(8)
        self.totals = _wrap(QLabel())
        self.table = QTableWidget(0, 4)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMaximumHeight(200)
        row = QHBoxLayout()
        self.cache_label = QLabel(objectName="StatHint")
        self.clear_btn = QPushButton()
        self.clear_btn.clicked.connect(self._clear_cache)
        row.addWidget(self.cache_label, 1)
        row.addWidget(self.clear_btn)
        self.note = _wrap(QLabel(objectName="StatHint"))
        for w in (self.limit_label, self.limit_bar, self.totals, self.table):
            self.body.addWidget(w)
        self.body.addLayout(row)
        self.body.addWidget(self.note)

    def confirm(self, title: str, text: str) -> bool:
        return QMessageBox.question(self, title, text) == QMessageBox.StandardButton.Yes

    def _clear_cache(self) -> None:
        if self.confirm(tr("usage.clear_cache"), tr("usage.clear_cache_confirm")):
            request_cache.clear(self.ctx.db)
            self.render()

    def render(self) -> None:
        db, limit = self.ctx.db, self.ctx.settings().limits.max_requests_per_day
        self.set_title(tr("usage.title"), tr("usage.subtitle"))
        used = usage_tracker.requests_today(db)
        self.limit_label.setText(tr("usage.today_limit", used=used, limit=limit))
        self.limit_bar.setRange(0, max(1, limit))
        self.limit_bar.setValue(min(used, limit))
        lines = []
        for days in (1, 7, 30):
            s = usage_tracker.summary(db, days)
            fails = sum(s.failures.values())
            lines.append(tr("usage.period", period=tr(f"usage.days_{days}"), sent=s.sent, cache=s.cache_hits,
                            failed=fails, tin=s.tokens_in, tout=s.tokens_out))
        month = usage_tracker.summary(db, 30)
        if month.failures:
            lines.append(tr("usage.failures") + " " + ", ".join(f"{tr(k)} ×{n}" for k, n in month.failures.most_common(4)))
        self.totals.setText("\n".join(lines))
        self.table.setHorizontalHeaderLabels([tr("usage.col.date"), tr("usage.col.sent"), tr("usage.col.cache"),
                                              tr("usage.col.failed")])
        rows = usage_tracker.summary(db, 7).per_day
        self.table.setRowCount(len(rows))
        for r, values in enumerate(rows):
            for c, v in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(str(v)))
        self.table.setVisible(bool(rows))
        self.cache_label.setText(tr("usage.cache_count", n=request_cache.count(db)))
        self.clear_btn.setText(tr("usage.clear_cache"))
        self.note.setText(tr("usage.note"))


class KnowledgeCard(Card):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.running = False
        self.feedback: str = ""
        self.summary = _wrap(QLabel())
        self.entries = _wrap(QLabel())
        self.entries.setTextFormat(Qt.TextFormat.RichText)
        self.entries.setOpenExternalLinks(True)
        row = QHBoxLayout()
        self.update_btn = QPushButton(objectName="PrimaryButton")
        self.update_btn.clicked.connect(self.start_update)
        self.feedback_label = _wrap(QLabel())
        row.addWidget(self.update_btn)
        row.addWidget(self.feedback_label, 1)
        self.note = _wrap(QLabel(objectName="StatHint"))
        for w in (self.summary, self.entries):
            self.body.addWidget(w)
        self.body.addLayout(row)
        self.body.addWidget(self.note)

    def confirm(self, title: str, text: str) -> bool:
        return QMessageBox.question(self, title, text) == QMessageBox.StandardButton.Yes

    def start_update(self) -> None:
        from fortnite_coach.ai.knowledge_updater import update_knowledge

        if self.running or self.ctx.gemini_status() is not GeminiStatus.CONNECTED:
            return
        settings = self.ctx.settings()
        if not self.confirm(tr("knowledge.update"), tr("knowledge.confirm", model=settings.gemini.model,
                                                        used=usage_tracker.requests_today(self.ctx.db),
                                                        limit=settings.limits.max_requests_per_day)):
            return
        self.running, self.feedback = True, tr("knowledge.running")
        self.render()
        service = self.ctx.gemini_service()
        run_task(lambda: update_knowledge(self.ctx.db, service, settings.limits), self._done, self._failed)

    def _done(self, result) -> None:
        self.running = False
        self.feedback = tr("knowledge.done", stored=result.stored, dropped=result.dropped)
        self.ctx.data_changed()
        self.render()

    def _failed(self, err) -> None:
        self.running = False
        self.feedback = "⚠  " + tr(getattr(err, "i18n_key", "error.generic"), **getattr(err, "params", {}))
        self.render()

    def render(self) -> None:
        db = self.ctx.db
        self.set_title(tr("knowledge.title"), tr("knowledge.subtitle"))
        all_current = knowledge_repo.current_entries(db)
        fundamentals = [e for e in all_current if e.kind == "fundamental"]
        season = [e for e in all_current if e.kind == "season_specific"]
        last = max((e.retrieved_at for e in season if e.retrieved_at), default=None)
        self.summary.setText(tr("knowledge.summary", fundamentals=len(fundamentals), season=len(season),
                                last=f"{last:%Y-%m-%d}" if last else tr("knowledge.never")))
        rows = []
        for e in season[:12]:
            stale = knowledge_repo.is_stale(e)
            mark = f" <span style='color:#F59E0B'>({tr('knowledge.stale')})</span>" if stale else ""
            date = f"{e.retrieved_at:%Y-%m-%d}" if e.retrieved_at else "?"
            src = f"<a href='{e.source_url}' style='color:#A78BFA'>{e.source_name or e.source_url}</a>" if e.source_url else ""
            ver = f" · {e.game_version}" if e.game_version else ""
            rows.append(f"• <b>{e.title}</b>{ver} — {e.content}<br>&nbsp;&nbsp;{date} · {src}{mark}")
        self.entries.setText("<br>".join(rows))
        self.entries.setVisible(bool(rows))
        connected = self.ctx.gemini_status() is GeminiStatus.CONNECTED
        self.update_btn.setText(tr("knowledge.running") if self.running else tr("knowledge.update"))
        self.update_btn.setEnabled(connected and not self.running)
        self.feedback_label.setText(self.feedback or ("" if connected else tr("knowledge.needs_key")))
        self.note.setText(tr("knowledge.note", days=knowledge_repo.FRESH_DAYS))


class AboutCard(Card):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.running = False
        self.result_text = ""
        self.info = _wrap(QLabel())
        self.info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row = QHBoxLayout()
        self.selftest_btn = QPushButton()
        self.selftest_btn.clicked.connect(self.run_self_test)
        self.privacy_btn = QPushButton()
        self.privacy_btn.clicked.connect(lambda: _open(docs_path("PRIVACY.md")))
        self.live_btn = QPushButton()
        self.live_btn.clicked.connect(lambda: _open(docs_path("LIVE_COACH.md")))
        self.logs_btn = QPushButton()
        self.logs_btn.clicked.connect(lambda: _open(self.ctx.paths.logs_dir))
        for b in (self.selftest_btn, self.privacy_btn, self.live_btn, self.logs_btn):
            row.addWidget(b)
        row.addStretch(1)
        self.result = _wrap(QLabel())
        self.privacy = _wrap(QLabel(objectName="StatHint"))
        self.body.addWidget(self.info)
        self.body.addLayout(row)
        self.body.addWidget(self.result)
        self.body.addWidget(self.privacy)

    def run_self_test(self) -> None:
        from fortnite_coach.selftest import run_self_test

        if self.running:
            return
        self.running = True
        self.result_text = tr("about.selftest_running")
        self.render()
        run_task(run_self_test, self._done, self._failed)

    def _done(self, report: dict) -> None:
        self.running = False
        lines = [("✓ " if c["ok"] else ("✗ " if c["required"] else "• ")) + tr(f"about.check.{c['check']}")
                 for c in report["checks"]]
        head = tr("about.selftest_ok") if report["ok"] else tr("about.selftest_fail")
        self.result_text = head + "\n" + "   ".join(lines)
        self.render()

    def _failed(self, err) -> None:
        self.running = False
        self.result_text = tr("about.selftest_fail") + f" ({type(err).__name__})"
        self.render()

    def render(self) -> None:
        p = self.ctx.paths
        self.set_title(tr("about.title"), tr("about.subtitle"))
        self.info.setText(tr("about.info", version=__version__, data=str(p.root), logs=str(p.logs_dir / "app.log")))
        self.selftest_btn.setText(tr("about.selftest"))
        self.selftest_btn.setEnabled(not self.running)
        self.privacy_btn.setText(tr("about.privacy"))
        self.live_btn.setText(tr("about.live_coach"))
        self.logs_btn.setText(tr("about.logs"))
        self.privacy_btn.setVisible(docs_path("PRIVACY.md").exists())
        self.live_btn.setVisible(docs_path("LIVE_COACH.md").exists())
        self.result.setText(self.result_text)
        self.privacy.setText(tr("about.privacy_summary") + "\n" + tr("about.live_status"))
