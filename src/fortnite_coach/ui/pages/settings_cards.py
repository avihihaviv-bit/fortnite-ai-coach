"""Extra Settings cards: API usage, knowledge updates, about/privacy/self-test."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
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


class LiveCard(Card):
    """Live Coach settings. Off until the player reads the limits and ticks the box."""

    saved = Signal()

    def __init__(self, ctx: AppContext):
        from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QSpinBox

        from fortnite_coach.ui.widgets.hotkey_edit import HotkeyEdit

        super().__init__()
        self.ctx = ctx
        self.warning = _wrap(QLabel(objectName="ReasonBox"))
        self.ack = QCheckBox()
        self.ack.toggled.connect(self._ack_toggled)
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        self.labels = {k: QLabel() for k in ("model", "interval", "frames", "max", "show", "hotkey")}
        self.model_combo = QComboBox()
        self.interval = QSpinBox()
        self.interval.setRange(15, 120)
        self.frames = QSpinBox()
        self.frames.setRange(2, 10)
        self.max_day = QSpinBox()
        self.max_day.setRange(1, 500)
        self.show_s = QSpinBox()
        self.show_s.setRange(4, 60)
        self.hotkey = HotkeyEdit()
        for k, w in (("model", self.model_combo), ("interval", self.interval), ("frames", self.frames), ("max", self.max_day),
                     ("show", self.show_s), ("hotkey", self.hotkey)):
            form.addRow(self.labels[k], w)
        for spin in (self.interval, self.frames, self.max_day, self.show_s):
            spin.valueChanged.connect(lambda _v: self.save())
        self.model_combo.activated.connect(lambda _i: self.save())
        self.hotkey.textChanged.connect(lambda _t: self.save())
        row = QHBoxLayout()
        self.save_btn = QPushButton(objectName="PrimaryButton")
        self.save_btn.clicked.connect(self.save)
        self.preview_btn = QPushButton()
        self.preview_btn.clicked.connect(lambda: self.ctx.preview_tip(tr("live.preview_text")))
        row.addWidget(self.save_btn)
        row.addWidget(self.preview_btn)
        row.addStretch(1)
        self.feedback = _wrap(QLabel(objectName="StatHint"))
        self.body.addWidget(self.warning)
        self.body.addWidget(self.ack)
        self.body.addLayout(form)
        self.body.addLayout(row)
        self.body.addWidget(self.feedback)
        self._msg = ""
        self.load()

    _loading = False

    def load(self) -> None:
        self._loading = True  # filling the fields must not save half-loaded values
        try:
            self._load()
        finally:
            self._loading = False

    def _load(self) -> None:
        lv = self.ctx.settings().live
        self.ack.blockSignals(True)
        self.ack.setChecked(lv.acknowledged)
        self.ack.blockSignals(False)
        self.interval.setValue(lv.interval_s)
        self.frames.setValue(lv.frames)
        self.max_day.setValue(lv.max_tips_per_day)
        self.show_s.setValue(lv.show_seconds)
        self.hotkey.setText(lv.hotkey)
        self._fill_models()

    def _fill_models(self) -> None:
        from fortnite_coach.ai.gemini_config import usable_models

        s = self.ctx.settings()
        current = self.model_combo.currentData() if self.model_combo.count() else s.live.model
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItem(tr("live.model_auto"), "")
        names = usable_models(s.gemini.available_models) or [s.gemini.model]
        if current and current not in names:
            names.append(current)
        for n in names:
            self.model_combo.addItem(n, n)
        self.model_combo.setCurrentIndex(max(0, self.model_combo.findData(current)))
        self.model_combo.blockSignals(False)

    def _ack_toggled(self, on: bool) -> None:
        """The tick is the on/off switch: it takes effect at once, no Save click needed."""
        if self._loading:
            return
        s = self.ctx.settings()
        if s.live.acknowledged == on:
            return
        lv = s.live.model_copy()
        lv.acknowledged = on
        s.live = lv
        self.ctx.save_settings(s)
        self._msg = tr("live.enabled" if on else "live.disabled")
        self.saved.emit()
        self.render()

    def save(self) -> None:
        from fortnite_coach.recording.hotkeys import HotkeyError, parse_hotkey

        if self._loading:
            return
        s = self.ctx.settings()
        key = self.hotkey.text().strip()
        try:
            combo = parse_hotkey(key)
            taken = [parse_hotkey(s.recording.hotkey_start), parse_hotkey(s.recording.hotkey_stop)]
            if s.recording.hotkey_toggle:
                taken.append(parse_hotkey(s.recording.hotkey_toggle))
            if combo in taken:
                raise HotkeyError("same")
        except HotkeyError:
            key = None  # keep the previous hotkey; the other values are still saved
        lv = s.live.model_copy()
        lv.acknowledged = self.ack.isChecked()
        lv.interval_s, lv.frames = self.interval.value(), self.frames.value()
        lv.max_tips_per_day, lv.show_seconds = self.max_day.value(), self.show_s.value()
        if key is not None:
            lv.hotkey = key
        lv.model = self.model_combo.currentData() or ""
        s.live = lv
        self.ctx.save_settings(s)
        self._msg = tr("live.saved") if key is not None else "⚠  " + tr("live.err_hotkey")
        self.saved.emit()
        self.render()

    def render(self) -> None:
        s = self.ctx.settings()
        self.set_title(tr("live.title"), tr("live.subtitle"))
        self.warning.setText(tr("live.warning"))
        self.ack.setText(tr("live.ack"))
        for k in self.labels:
            self.labels[k].setText(tr(f"live.f_{k}"))
        self.interval.setSuffix(" " + tr("live.sec"))
        self.show_s.setSuffix(" " + tr("live.sec"))
        self.save_btn.setText(tr("common.save"))
        self.save_btn.hide()  # saved automatically
        self.preview_btn.setText(tr("live.preview"))
        from fortnite_coach.ai.gemini_config import live_model

        self._fill_models()  # the model list changes after Test connection / language change
        picked = live_model(s.gemini.available_models, s.gemini.model, s.live.model)
        used = usage_tracker.live_requests_today(self.ctx.db)
        per_hour = 3600 // max(1, s.live.interval_s)
        lines = [tr("live.usage", used=used, limit=s.live.max_tips_per_day, per_hour=per_hour),
                 tr("live.model_note_lite" if picked != s.gemini.model else "live.model_note_same", model=picked)]
        if self._msg:
            lines.insert(0, self._msg)
        self.feedback.setText("\n".join(lines))


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


class UpdateCard(Card):
    """Check for updates / install: downloads the new installer from this project's GitHub Releases,
    verifies its SHA-256, runs it (it closes the app, upgrades and starts it again)."""

    def __init__(self, ctx: AppContext):
        from fortnite_coach import updater

        super().__init__()
        self.ctx = ctx
        self.updater = updater
        self.info = None            # UpdateInfo when a newer version exists
        self.state = "idle"         # idle | checking | latest | available | downloading | error | installing
        self.error = ""
        self.cancel = None
        self.status = _wrap(QLabel())
        self.notes = _wrap(QLabel(objectName="StatHint"))
        row = QHBoxLayout()
        self.check_btn = QPushButton()
        self.check_btn.clicked.connect(lambda: self.check(manual=True))
        self.install_btn = QPushButton(objectName="PrimaryButton")
        self.install_btn.clicked.connect(self.install)
        self.cancel_btn = QPushButton()
        self.cancel_btn.clicked.connect(lambda: self.cancel and self.cancel.set())
        for b in (self.check_btn, self.install_btn, self.cancel_btn):
            row.addWidget(b)
        row.addStretch(1)
        self.bar = QProgressBar()
        self.bar.hide()
        self.body.addWidget(self.status)
        self.body.addLayout(row)
        self.body.addWidget(self.bar)
        self.body.addWidget(self.notes)

    def confirm(self, title: str, text: str) -> bool:
        return QMessageBox.question(self, title, text) == QMessageBox.StandardButton.Yes

    def check(self, manual: bool = False, on_found=None) -> None:
        if self.state in ("checking", "downloading", "installing"):
            return
        self.state, self.error = "checking", ""
        self.render()

        def done(info):
            self.info = info
            self.state = "available" if info else "latest"
            self.render()
            if info and on_found:
                on_found(info)

        def failed(err):
            self.state = "error" if manual else "idle"
            self.error = tr(getattr(err, "i18n_key", "update.err_network"))
            self.render()

        run_task(self.updater.check, done, failed)

    def busy_reason(self) -> str | None:
        win = self.window()
        if getattr(getattr(win, "recording", None), "is_recording", False) or \
                getattr(getattr(win, "live", None), "active", False):
            return "update.busy_recording"
        for key in ("gameplay", "training_sessions"):
            page = getattr(win, "pages", {}).get(key)
            if page is not None and page.job is not None and page.job.running:
                return "update.busy_analysis"
        return None

    def install(self) -> None:
        import threading

        if self.info is None or self.state in ("downloading", "installing"):
            return
        if not self.updater.can_self_update():
            self.state, self.error = "error", tr("update.err_not_installed")
            self.render()
            return
        reason = self.busy_reason()
        if reason:
            self.state, self.error = "error", tr(reason)
            self.render()
            return
        mb = f"{self.info.size / 1_048_576:.0f}" if self.info.size else "?"
        if not self.confirm(tr("update.title"), tr("update.confirm", version=self.info.version, mb=mb)):
            return
        self.state, self.cancel = "downloading", threading.Event()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.render()
        info, folder, cancel = self.info, self.ctx.paths.cache_dir / "updates", self.cancel
        def progress(done, total):
            self._progress = (done, total)

        self._progress = (0, 0)
        from PySide6.QtCore import QTimer

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._show_progress)
        self._tick.start(300)
        run_task(lambda: self.updater.download(info, folder, progress, cancel), self._downloaded, self._failed)

    def _show_progress(self) -> None:
        done, total = self._progress
        if total:
            self.bar.setValue(int(done * 100 / total))
            self.status.setText(tr("update.downloading", done=f"{done / 1_048_576:.0f}", total=f"{total / 1_048_576:.0f}"))

    def _downloaded(self, path) -> None:
        self._tick.stop()
        self.state = "installing"
        self.render()
        try:
            self.updater.launch_installer(path)
        except Exception as e:
            self.state, self.error = "error", tr(getattr(e, "i18n_key", "update.err_launch"))
            self.render()
            return
        win = self.window()
        if hasattr(win, "quit_app"):
            win.quit_app()  # the installer replaces the files and starts the new version

    def _failed(self, err) -> None:
        if hasattr(self, "_tick"):
            self._tick.stop()
        key = getattr(err, "i18n_key", "update.err_network")
        self.state = "idle" if key == "update.cancelled" else "error"
        self.error = "" if key == "update.cancelled" else tr(key)
        self.render()

    def render(self) -> None:
        self.set_title(tr("update.title"), tr("update.subtitle", version=__version__))
        st = self.state
        text = {
            "idle": tr("update.idle"),
            "checking": tr("update.checking"),
            "latest": tr("update.latest", version=__version__),
            "available": tr("update.available", version=self.info.version if self.info else "?"),
            "downloading": tr("update.downloading", done="0", total="?"),
            "installing": tr("update.installing"),
            "error": "⚠  " + self.error,
        }[st]
        if st != "downloading" or not getattr(self, "_progress", (0, 0))[1]:
            self.status.setText(text)
        self.check_btn.setText(tr("update.check"))
        self.check_btn.setEnabled(st not in ("checking", "downloading", "installing"))
        self.install_btn.setText(tr("update.install", version=self.info.version) if self.info else tr("update.install_plain"))
        self.install_btn.setVisible(self.info is not None and st in ("available", "error"))
        self.cancel_btn.setText(tr("common.cancel"))
        self.cancel_btn.setVisible(st == "downloading")
        self.bar.setVisible(st == "downloading")
        notes = (self.info.notes.strip() if self.info else "")
        self.notes.setText(tr("update.notes", notes=notes[:600]) if notes and st in ("available", "error") else
                           tr("update.how"))
