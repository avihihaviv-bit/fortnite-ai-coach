"""Clip library: videos you already have (Medal, NVIDIA, Xbox Game Bar, OBS, this app) - open one, or analyze several."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QProgressBar,
    QPushButton, QWidget,
)
from sqlalchemy import func, select

from fortnite_coach.ai import usage_tracker
from fortnite_coach.ai.status import GeminiStatus
from fortnite_coach.core.game_modes import AnalysisDepth, GameMode
from fortnite_coach.db.models import Report, Session, Video
from fortnite_coach.i18n.translator import get_translator, tr
from fortnite_coach.library import clips as clip_lib
from fortnite_coach.recording import process_guard
from fortnite_coach.ui.context import AppContext
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.ui.widgets.empty_state import EmptyState
from fortnite_coach.workers.task import run_task

MAX_BATCH = 10


def _fmt_size(n: int) -> str:
    return f"{n / 1_048_576:.0f} MB" if n < 1_073_741_824 else f"{n / 1_073_741_824:.1f} GB"


class ClipsPage(BasePage):
    page_key = "clips"

    def __init__(self, ctx: AppContext, open_clip, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.open_clip = open_clip  # callable(path): load it in the analysis page
        self.clips: list[clip_lib.Clip] = []
        self.scanning = False
        self.job = None
        self.results: list = []
        self.message = ""
        self.home: Path | None = None  # tests override

        # ---- folders ----
        self.folders_card = Card()
        self.folder_list = QListWidget()
        self.folder_list.setMaximumHeight(130)
        frow = QHBoxLayout()
        self.add_btn = QPushButton()
        self.add_btn.clicked.connect(self._choose_folder)
        self.remove_btn = QPushButton()
        self.remove_btn.clicked.connect(self._remove_folder)
        self.scan_btn = QPushButton(objectName="PrimaryButton")
        self.scan_btn.clicked.connect(self.rescan)
        for b in (self.add_btn, self.remove_btn, self.scan_btn):
            frow.addWidget(b)
        frow.addStretch(1)
        self.folders_hint = QLabel(objectName="StatHint")
        self.folders_hint.setWordWrap(True)
        self.folders_card.body.addWidget(self.folder_list)
        self.folders_card.body.addLayout(frow)
        self.folders_card.body.addWidget(self.folders_hint)
        self.content.addWidget(self.folders_card)

        # ---- clips ----
        self.clips_card = Card()
        self.clip_list = QListWidget()
        self.clip_list.setMinimumHeight(260)
        self.clip_list.itemDoubleClicked.connect(lambda it: self.open_clip(it.data(Qt.ItemDataRole.UserRole)))
        self.clip_list.itemChanged.connect(lambda _it: self._render_actions())
        self.empty = EmptyState("gameplay")
        crow = QHBoxLayout()
        self.open_btn = QPushButton()
        self.open_btn.clicked.connect(self._open_current)
        self.mode_combo = QComboBox()
        for m in GameMode:
            self.mode_combo.addItem("", m.value)
        self.depth_combo = QComboBox()
        for d in AnalysisDepth:
            self.depth_combo.addItem("", d.value)
        self.depth_combo.setCurrentIndex(list(AnalysisDepth).index(AnalysisDepth.STANDARD))
        self.analyze_btn = QPushButton(objectName="PrimaryButton")
        self.analyze_btn.clicked.connect(self.start_batch)
        self.cancel_btn = QPushButton(objectName="DangerButton")
        self.cancel_btn.clicked.connect(self.cancel_batch)
        for w in (self.open_btn, self.mode_combo, self.depth_combo, self.analyze_btn, self.cancel_btn):
            crow.addWidget(w)
        crow.addStretch(1)
        self.progress = QProgressBar()
        self.progress.hide()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.results_list = QListWidget()
        self.results_list.setMaximumHeight(160)
        self.results_list.itemActivated.connect(self._open_result)
        self.results_list.itemDoubleClicked.connect(self._open_result)
        self.results_list.hide()
        for w in (self.clip_list, self.empty):
            self.clips_card.body.addWidget(w)
        self.clips_card.body.addLayout(crow)
        for w in (self.progress, self.status, self.results_list):
            self.clips_card.body.addWidget(w)
        self.content.addWidget(self.clips_card)
        self.finish()
        self._render_folders()

    # ---------------- folders ----------------
    def folders(self) -> list[tuple[str, Path]]:
        out = clip_lib.detected_folders(self.home)
        known = {str(p).lower() for _, p in out}
        for f in self.ctx.settings().clip_folders:
            if str(Path(f)).lower() not in known:
                out.append(("clips.src_custom", Path(f)))
        return out

    def add_folder(self, path: str) -> None:
        s = self.ctx.settings()
        if path and path not in s.clip_folders:
            s.clip_folders = [*s.clip_folders, path]
            self.ctx.save_settings(s)
        self._render_folders()
        self.rescan()

    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("clips.add_folder"))
        if path:
            self.add_folder(path)

    def _remove_folder(self) -> None:
        it = self.folder_list.currentItem()
        if it is None:
            return
        path = it.data(Qt.ItemDataRole.UserRole)
        s = self.ctx.settings()
        if path in s.clip_folders:
            s.clip_folders = [f for f in s.clip_folders if f != path]
            self.ctx.save_settings(s)
        self._render_folders()
        self.rescan()

    def _render_folders(self) -> None:
        self.folder_list.clear()
        custom = set(self.ctx.settings().clip_folders)
        for key, p in self.folders():
            it = QListWidgetItem(f"{tr(key)}   ·   {p}")
            it.setData(Qt.ItemDataRole.UserRole, str(p))
            self.folder_list.addItem(it)
        self.remove_btn.setEnabled(bool(custom))

    # ---------------- clips ----------------
    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self.clips and not self.scanning:
            self.rescan()

    def rescan(self) -> None:
        if self.scanning:
            self._rescan_again = True  # folders changed during a scan: scan once more when it ends
            return
        self._rescan_again = False
        self.scanning = True
        pairs = self.folders()
        folders = [p for _, p in pairs]
        shallow = {str(p) for k, p in pairs if k == "clips.src_videos"}
        self._render_actions()
        run_task(lambda: clip_lib.scan(folders, shallow=shallow), self._scanned, lambda _e: self._scanned([]))

    def _scanned(self, clips) -> None:
        self.scanning = False
        if getattr(self, "_rescan_again", False):
            self.rescan()
        self.clips = clips
        analyzed = self._analyzed_paths()
        self.clip_list.blockSignals(True)
        self.clip_list.clear()
        for c in clips:
            mark = "   ✓ " + tr("clips.analyzed") if c.path.lower() in analyzed else ""
            it = QListWidgetItem(f"{c.name}   ·   {_fmt_size(c.size_bytes)}   ·   {c.modified:%Y-%m-%d %H:%M}{mark}")
            it.setData(Qt.ItemDataRole.UserRole, c.path)
            it.setToolTip(c.path)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Unchecked)
            self.clip_list.addItem(it)
        self.clip_list.blockSignals(False)
        self._render_actions()

    def _analyzed_paths(self) -> set[str]:
        with self.ctx.db.session() as s:
            rows = s.execute(select(Video.path).join(Session, Session.video_id == Video.id)
                             .join(Report, Report.session_id == Session.id).group_by(Video.path)
                             .having(func.count(Report.id) > 0)).all()
        return {r[0].lower() for r in rows}

    def checked_paths(self) -> list[str]:
        return [self.clip_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.clip_list.count())
                if self.clip_list.item(i).checkState() == Qt.CheckState.Checked]

    def set_checked(self, paths: list[str]) -> None:
        for i in range(self.clip_list.count()):
            it = self.clip_list.item(i)
            it.setCheckState(Qt.CheckState.Checked if it.data(Qt.ItemDataRole.UserRole) in paths
                             else Qt.CheckState.Unchecked)

    def _open_current(self) -> None:
        it = self.clip_list.currentItem()
        checked = self.checked_paths()
        path = it.data(Qt.ItemDataRole.UserRole) if it else (checked[0] if checked else None)
        if path:
            self.open_clip(path)

    # ---------------- batch ----------------
    def confirm(self, title: str, text: str) -> bool:
        return QMessageBox.question(self, title, text) == QMessageBox.StandardButton.Yes

    def batch_block_reason(self) -> str | None:
        n = len(self.checked_paths())
        if n == 0:
            return "clips.need_selection"
        if n > MAX_BATCH:
            return "clips.too_many"
        status = self.ctx.gemini_status()
        if status is GeminiStatus.NOT_CONFIGURED:
            return "analysis.need_key"
        if status is not GeminiStatus.CONNECTED:
            return "analysis.need_test"
        if self.job is not None and self.job.running:
            return "analysis.running"
        return None

    def start_batch(self) -> None:
        from fortnite_coach.library.batch import BatchJob

        if self.batch_block_reason() is not None:
            return
        if process_guard.is_fortnite_running():
            if not self.confirm(tr("analysis.fortnite_running_title"), tr("analysis.fortnite_running_confirm")):
                return
        settings = self.ctx.settings()
        self.results, self.message = [], ""
        self.job = BatchJob(self.ctx.db, self.ctx.paths, settings)
        self.job.progress.connect(self._on_progress)
        self.job.prepared.connect(self._on_prepared)
        self.job.finished.connect(self._on_finished)
        self.job.failed.connect(self._on_failed)
        self.progress.show()
        self.job.start_prepare(self.checked_paths(), GameMode(self.mode_combo.currentData()),
                               AnalysisDepth(self.depth_combo.currentData()), get_translator().language)
        self._render_actions()

    def _on_progress(self, step: str, i: int, n: int) -> None:
        self.progress.setRange(0, n)
        self.progress.setValue(i)
        self.status.setText(tr(step, i=i, n=n))

    def _on_prepared(self, items) -> None:
        settings = self.ctx.settings()
        ok = [p for p in items if p.request is not None]
        bad = len(items) - len(ok)
        to_send = sum(p.to_send for p in ok)
        text = tr("clips.confirm", clips=len(ok), requests=to_send, cached=sum(p.cached for p in ok),
                  model=settings.gemini.model, used=usage_tracker.requests_today(self.ctx.db),
                  limit=settings.limits.max_requests_per_day)
        if bad:
            text += "\n" + tr("clips.unreadable", n=bad)
        if not ok or not self.confirm(tr("clips.analyze"), text):
            self.progress.hide()
            self.message = tr("clips.unreadable", n=bad) if not ok else tr("clips.cancelled")
            self._render_actions()
            return
        self.job.start_analyze(self.ctx.gemini_service())
        self._render_actions()

    def _on_finished(self, res) -> None:
        self.progress.hide()
        self.results = res.items
        ok = sum(1 for r in res.items if r.report_id)
        self.message = tr("clips.done", ok=ok, n=len(res.items))
        if res.stopped_reason:
            self.message += "\n⚠  " + tr("clips.stopped", reason=tr(res.stopped_reason))
        self.results_list.clear()
        for r in res.items:
            name = Path(r.path).name
            text = (f"✓  {name}   ·   {tr('clips.open_report')}" if r.report_id
                    else f"⚠  {name}   ·   {tr(r.error or 'error.generic')}")
            it = QListWidgetItem(text)
            it.setData(Qt.ItemDataRole.UserRole, r.report_id)
            self.results_list.addItem(it)
        self.results_list.setVisible(bool(res.items))
        self.ctx.data_changed()
        self._scanned(self.clips)

    def _on_failed(self, err) -> None:
        self.progress.hide()
        self.message = "⚠  " + tr(getattr(err, "i18n_key", "error.generic"))
        self._render_actions()

    def cancel_batch(self) -> None:
        if self.job is not None and self.job.running:
            self.job.cancel()
            self.status.setText(tr("job.cancelling"))

    def _open_result(self, it) -> None:
        rid = it.data(Qt.ItemDataRole.UserRole)
        if rid:
            self.ctx.open_report(rid)

    # ---------------- render ----------------
    def _render_actions(self) -> None:
        has = bool(self.clips)
        self.clip_list.setVisible(has)
        self.empty.setVisible(not has)
        running = self.job is not None and self.job.running
        reason = self.batch_block_reason()
        n = len(self.checked_paths())
        self.analyze_btn.setText(tr("clips.analyze_n", n=n) if n else tr("clips.analyze"))
        self.analyze_btn.setEnabled(reason is None)
        self.cancel_btn.setVisible(running)
        self.open_btn.setEnabled(has and not running)
        self.scan_btn.setEnabled(not self.scanning)
        if running:
            return
        lines = []
        if self.scanning:
            lines.append(tr("clips.scanning"))
        elif has:
            lines.append(tr("clips.count", n=len(self.clips)))
        if self.message:
            lines.append(self.message)
        elif reason and reason != "clips.need_selection" and has:
            lines.append(tr(reason, max=MAX_BATCH))
        self.status.setText("\n".join(lines))

    def retranslate(self) -> None:
        super().retranslate()
        self.folders_card.set_title(tr("clips.folders"), tr("clips.folders_sub"))
        self.clips_card.set_title(tr("clips.list"), tr("clips.list_sub"))
        self.add_btn.setText(tr("clips.add_folder"))
        self.remove_btn.setText(tr("clips.remove_folder"))
        self.scan_btn.setText(tr("clips.rescan"))
        self.folders_hint.setText(tr("clips.folders_hint"))
        self.open_btn.setText(tr("clips.open"))
        self.cancel_btn.setText(tr("analysis.cancel"))
        self.empty.set_text(tr("clips.empty_title"), tr("clips.empty_text"))
        for i, m in enumerate(GameMode):
            self.mode_combo.setItemText(i, tr(f"mode.{m.value}"))
        for i, d in enumerate(AnalysisDepth):
            self.depth_combo.setItemText(i, tr(f"depth.{d.value}"))
        if hasattr(self, "folder_list"):
            self._render_folders()
            self._render_actions()
