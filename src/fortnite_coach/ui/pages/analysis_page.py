"""Gameplay Analysis / Training Sessions page.

Record (user-controlled) or import a finished video, preview it, read measured
metadata, choose mode/depth/focus and see exactly which part will be analyzed.
The Analyze button stays disabled until Gemini is connected; nothing is simulated.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QWidget,
)
from sqlalchemy import select

from fortnite_coach.ai.status import GeminiStatus
from fortnite_coach.core.errors import CoachError
from fortnite_coach.core.game_modes import TRAINING_MODES, AnalysisDepth, GameMode
from fortnite_coach.core.skills import SKILL_PAGES
from fortnite_coach.db.models import Video
from fortnite_coach.db.repositories import session_repo
from fortnite_coach.i18n.translator import tr
from fortnite_coach.recording.hotkeys import is_supported as hotkeys_supported
from fortnite_coach.ui.context import AppContext
from fortnite_coach.ui.pages.base import BasePage
from fortnite_coach.ui.widgets.card import Card
from fortnite_coach.ui.widgets.empty_state import EmptyState
from fortnite_coach.ui.widgets.status_pill import StatusPill
from fortnite_coach.video.importer import ImportedVideo, import_video
from fortnite_coach.video.segments import coverage, plan_segments
from fortnite_coach.workers.task import run_task
from fortnite_coach.recording import process_guard


def fmt_duration(seconds: float) -> str:
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class AnalysisPage(BasePage):
    video_imported = Signal()
    analysis_finished = Signal(str)  # message for the tray when the app is in the background

    def __init__(self, ctx: AppContext, *, training: bool, parent: QWidget | None = None):
        self.page_key = "training_sessions" if training else "gameplay"
        self.ctx = ctx
        self.training = training
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.current: ImportedVideo | None = None
        self.loading = False
        self.error_key: str | None = None

        # --- record + import row ---
        top = QHBoxLayout()
        top.setSpacing(16)
        self.rec_card = Card()
        self.rec_status = StatusPill()
        self.rec_time = QLabel(objectName="StatValue")
        rec_btns = QHBoxLayout()
        self.rec_start = QPushButton(objectName="PrimaryButton")
        self.rec_stop = QPushButton(objectName="DangerButton")
        self.rec_start.clicked.connect(self._start_recording)
        self.rec_stop.clicked.connect(ctx.recording.stop)
        self.rec_load = QPushButton()
        self.rec_load.clicked.connect(self.load_last_recording)
        rec_btns.addWidget(self.rec_start)
        rec_btns.addWidget(self.rec_stop)
        rec_btns.addWidget(self.rec_load)
        rec_btns.addStretch(1)
        self.rec_info = QLabel(objectName="StatHint")
        self.rec_info.setWordWrap(True)
        for w in (self.rec_status, self.rec_time):
            self.rec_card.body.addWidget(w)
        self.rec_card.body.addLayout(rec_btns)
        self.rec_card.body.addWidget(self.rec_info)
        top.addWidget(self.rec_card, 1)

        self.import_card = Card()
        self.import_btn = QPushButton(objectName="PrimaryButton")
        self.import_btn.clicked.connect(self._choose_file)
        self.import_hint = QLabel(objectName="StatHint")
        self.import_hint.setWordWrap(True)
        self.import_status = QLabel()
        self.import_status.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(self.import_btn)
        row.addStretch(1)
        self.import_card.body.addLayout(row)
        self.import_card.body.addWidget(self.import_hint)
        self.import_card.body.addWidget(self.import_status)
        top.addWidget(self.import_card, 1)
        self.content.addLayout(top)

        # --- loaded video ---
        self.video_card = Card()
        self.thumbs_row = QHBoxLayout()
        self.thumbs_row.setSpacing(8)
        self.thumb_labels = []
        for _ in range(4):
            lbl = QLabel()
            lbl.setFixedSize(220, 124)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("background:#0E0F12;border-radius:8px;")
            self.thumbs_row.addWidget(lbl)
            self.thumb_labels.append(lbl)
        self.thumbs_row.addStretch(1)
        self.video_card.body.addLayout(self.thumbs_row)
        self.meta_grid = QGridLayout()
        self.meta_grid.setHorizontalSpacing(24)
        self.meta_labels: dict[str, tuple[QLabel, QLabel]] = {}
        for i, key in enumerate(("duration", "resolution", "fps", "codec", "size", "audio")):
            k, v = QLabel(objectName="StatLabel"), QLabel()
            self.meta_grid.addWidget(k, 0, i)
            self.meta_grid.addWidget(v, 1, i)
            self.meta_labels[key] = (k, v)
        self.video_card.body.addLayout(self.meta_grid)
        vbtns = QHBoxLayout()
        self.open_player_btn = QPushButton()
        self.open_folder_btn = QPushButton()
        self.open_player_btn.clicked.connect(lambda: self._open(self.current.meta.path if self.current else None))
        self.open_folder_btn.clicked.connect(
            lambda: self._open(str(Path(self.current.meta.path).parent) if self.current else None))
        vbtns.addWidget(self.open_player_btn)
        vbtns.addWidget(self.open_folder_btn)
        vbtns.addStretch(1)
        self.video_card.body.addLayout(vbtns)
        self.content.addWidget(self.video_card)

        # --- analysis setup ---
        self.setup_card = Card()
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        self.mode_label, self.depth_label, self.focus_label = QLabel(), QLabel(), QLabel()
        self.mode_combo = QComboBox()
        modes = [m for m in GameMode if (m in TRAINING_MODES) == training] if training else list(GameMode)
        for m in modes:
            self.mode_combo.addItem("", m.value)
        self.depth_combo = QComboBox()
        for d in AnalysisDepth:
            self.depth_combo.addItem("", d.value)
        self.depth_combo.setCurrentIndex(1)
        self.depth_combo.currentIndexChanged.connect(self._render_coverage)
        focus_row = QHBoxLayout()
        self.focus_boxes: dict[str, QCheckBox] = {}
        for s in SKILL_PAGES:
            cb = QCheckBox()
            cb.setChecked(True)
            focus_row.addWidget(cb)
            self.focus_boxes[s.value] = cb
        focus_row.addStretch(1)
        form.addRow(self.mode_label, self.mode_combo)
        form.addRow(self.depth_label, self.depth_combo)
        form.addRow(self.focus_label, focus_row)
        self.setup_card.body.addLayout(form)
        self.coverage_label = QLabel()
        self.coverage_label.setWordWrap(True)
        self.setup_card.body.addWidget(self.coverage_label)
        arow = QHBoxLayout()
        self.analyze_btn = QPushButton(objectName="PrimaryButton")
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.clicked.connect(self.start_analysis)
        arow.addWidget(self.analyze_btn)
        arow.addStretch(1)
        self.setup_card.body.addLayout(arow)
        self.analyze_reason = QLabel(objectName="StatHint")
        self.analyze_reason.setWordWrap(True)
        self.setup_card.body.addWidget(self.analyze_reason)
        # progress (visible only while a user-started analysis runs)
        self.progress_box = QWidget()
        pl = QHBoxLayout(self.progress_box)
        pl.setContentsMargins(0, 0, 0, 0)
        self.progress_label = QLabel()
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.cancel_btn = QPushButton(objectName="DangerButton")
        self.cancel_btn.clicked.connect(self.cancel_analysis)
        pl.addWidget(self.progress_label, 2)
        pl.addWidget(self.progress_bar, 3)
        pl.addWidget(self.cancel_btn)
        self.progress_box.hide()
        self.setup_card.body.addWidget(self.progress_box)
        self.job = None
        self.job_error: str | None = None
        self.content.addWidget(self.setup_card)

        # --- recent videos ---
        self.recent_card = Card()
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(180)
        self.recent_list.itemActivated.connect(lambda it: self.load_path(it.data(Qt.ItemDataRole.UserRole)))
        self.recent_empty = EmptyState("history")
        self.recent_card.body.addWidget(self.recent_list)
        self.recent_card.body.addWidget(self.recent_empty)
        self.content.addWidget(self.recent_card)

        rc = ctx.recording
        rc.state_changed.connect(lambda _s: self._render_recording())
        rc.tick.connect(lambda _t: self._render_recording())
        rc.capabilities_ready.connect(lambda _c: self._render_recording())
        rc.finished.connect(self._on_recording_finished)
        rc.failed.connect(self._on_recording_failed)
        rc.interrupted.connect(lambda _n: self._render_recording())
        self._rec_error: str | None = None
        self._last_recording: list[str] | None = None  # parts of the last recording (joined on load)
        self._last_restarts = 0
        self.finish()
        self.refresh_recent()

    # ---------------- recording ----------------
    def showEvent(self, event) -> None:  # detect hardware the first time the user opens the page
        super().showEvent(event)
        rc = self.ctx.recording
        if rc.caps is None and not rc.detecting and rc.caps_error is None:
            rc.detect()
            self._render_recording()

    def _start_recording(self) -> None:
        self._rec_error = None
        self.ctx.recording.start()
        self._render_recording()

    def _on_recording_finished(self, parts) -> None:
        # Not processed automatically: the player may still be in a match. The user loads it when done.
        self._rec_error = None
        self._last_recording = [parts] if isinstance(parts, str) else list(parts)
        self._last_restarts = self.ctx.recording.recorder.restarts
        self._render_recording()

    def load_last_recording(self) -> None:
        """Join the parts (only now, after the game) and import the result."""
        from fortnite_coach.recording.merge import merge_parts

        parts = self._last_recording or []
        if self.loading or not parts:
            return
        self.loading, self.error_key = True, None
        self.import_status.setText(tr("rec.preparing"))
        self.import_btn.setEnabled(False)
        s = self.ctx.settings()

        def done(path):
            self.loading = False
            self._last_recording = [str(path)]
            self.load_path(str(path))

        def failed(err):
            self.loading = False
            self.error_key = getattr(err, "i18n_key", "video.err_merge")
            self._render_import()

        run_task(lambda: merge_parts(parts, ffmpeg=s.ffmpeg_path, ffprobe=s.ffprobe_path), done, failed)

    def _on_recording_failed(self, msg: str) -> None:
        self._rec_error = msg
        self._render_recording()

    def _render_recording(self) -> None:
        rc = self.ctx.recording
        rec = self.ctx.settings().recording
        self.rec_card.set_title(tr("rec.title"), tr("rec.subtitle"))
        if rc.is_recording:
            self.rec_status.set_state("error", tr("rec.recording"))
            self.rec_time.setText(fmt_duration(rc.recorder.elapsed_s))
        else:
            self.rec_status.set_state("off", tr("rec.idle"))
            self.rec_time.setText("00:00")
        self.rec_start.setText(tr("rec.start"))
        self.rec_stop.setText(tr("rec.stop"))
        self.rec_start.setEnabled(not rc.is_recording and rc.caps is not None and rc.caps.can_record)
        self.rec_stop.setEnabled(rc.is_recording)
        self.rec_load.setText(tr("rec.load_last"))
        self.rec_load.setVisible(bool(self._last_recording) and not rc.is_recording)
        lines: list[str] = []
        if self._last_recording and not rc.is_recording:
            folder = str(Path(self._last_recording[0]).parent)
            lines.append(tr("rec.saved_parts", n=len(self._last_recording), folder=folder)
                         if len(self._last_recording) > 1 else tr("rec.saved", path=self._last_recording[0]))
        restarts = rc.recorder.restarts if rc.is_recording else self._last_restarts
        if restarts:
            lines.append("⚠  " + tr("rec.interrupted", n=restarts))
        if rc.detecting:
            lines.append(tr("rec.detecting"))
        elif rc.caps_error:
            lines.append(tr(rc.caps_error))
        elif rc.caps is not None:
            if not rc.caps.can_record:
                lines.append(tr("rec.not_available"))
            else:
                enc = rc.chosen_encoder(rec) or ""
                hw = enc in ("h264_nvenc", "hevc_nvenc", "h264_amf", "h264_qsv")
                lines.append(tr("rec.using", encoder=enc, source=rc.caps.capture_backend))
                lines.append(tr("rec.hw_note") if hw else tr("rec.cpu_warning"))
                if not rec.audio_device:
                    lines.append(tr("rec.video_only"))
        if hotkeys_supported() and rec.hotkeys_enabled:
            lines.append(tr("rec.hotkeys", start=rec.hotkey_start, stop=rec.hotkey_stop))
            if rc.hotkey_errors:
                lines.append("⚠  " + tr("rec.hotkey_taken", keys=", ".join(rc.hotkey_errors)))
        elif not hotkeys_supported():
            lines.append(tr("rec.hotkeys_windows_only"))
        lines.append(tr("rec.fps_note"))
        if self._rec_error:
            lines.insert(0, tr(self._rec_error) if "." in self._rec_error and " " not in self._rec_error
                         else tr("rec.err_ffmpeg", detail=self._rec_error[-200:]))
        self.rec_info.setText("\n".join(lines))

    # ---------------- import ----------------
    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("video.choose"), "", tr("video.filter"))
        if path:
            self.load_path(path)

    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:
        urls = e.mimeData().urls()
        if urls:
            self.load_path(urls[0].toLocalFile())

    def load_path(self, path: str) -> None:
        if self.loading or not path:
            return
        self.loading, self.error_key = True, None
        self._render_import()
        frames_root = self.ctx.paths.frames_dir
        ffprobe = self.ctx.settings().ffprobe_path
        run_task(lambda: import_video(path, frames_root, ffprobe), self._import_done, self._import_failed)

    def _import_done(self, video: ImportedVideo) -> None:
        self.loading, self.current = False, video
        m = video.meta
        session_repo.upsert_video(self.ctx.db, session_repo.VideoInfo(
            path=m.path, fingerprint=video.fingerprint, size_bytes=m.size_bytes, duration_s=m.duration_s,
            width=m.width, height=m.height, fps=m.fps, codec=m.codec))
        self.refresh_recent()
        self.retranslate()
        self.video_imported.emit()

    def _import_failed(self, err: Exception) -> None:
        self.loading = False
        self.error_key = err.i18n_key if isinstance(err, CoachError) else "video.err_unreadable"
        self._render_import()

    def _render_import(self) -> None:
        self.import_card.set_title(tr("video.import_title"), tr("video.import_sub"))
        self.import_btn.setText(tr("video.choose"))
        self.import_btn.setEnabled(not self.loading)
        self.import_hint.setText(tr("video.import_hint"))
        if self.loading:
            self.import_status.setText(tr("common.loading"))
        elif self.error_key:
            self.import_status.setText("⚠  " + tr(self.error_key))
        elif self.current:
            self.import_status.setText(tr("video.loaded", name=Path(self.current.meta.path).name))
        else:
            self.import_status.setText("")

    def _open(self, target: str | None) -> None:
        if target:
            QDesktopServices.openUrl(QUrl.fromLocalFile(target))

    # ---------------- recent ----------------
    def refresh_recent(self) -> None:
        with self.ctx.db.session() as s:
            videos = list(s.scalars(select(Video).order_by(Video.imported_at.desc()).limit(10)))
        self.recent_list.clear()
        for v in videos:
            dur = fmt_duration(v.duration_s) if v.duration_s else "?"
            item = QListWidgetItem(f"{Path(v.path).name}   ·   {dur}   ·   {v.imported_at:%Y-%m-%d}")
            item.setData(Qt.ItemDataRole.UserRole, v.path)
            item.setToolTip(v.path)
            self.recent_list.addItem(item)
        self.recent_list.setVisible(bool(videos))
        self.recent_empty.setVisible(not videos)

    # ---------------- analysis setup ----------------
    def selected_mode(self) -> GameMode:
        return GameMode(self.mode_combo.currentData())

    def selected_depth(self) -> AnalysisDepth:
        return AnalysisDepth(self.depth_combo.currentData())

    def selected_focus(self) -> list[str]:
        return [k for k, cb in self.focus_boxes.items() if cb.isChecked()]

    def analyze_block_reason(self) -> str | None:
        """Why Analyze is disabled (i18n key), or None if it may run."""
        if self.current is None:
            return "analysis.need_video"
        status = self.ctx.gemini_status()
        if status is GeminiStatus.NOT_CONFIGURED:
            return "analysis.need_key"
        if status is not GeminiStatus.CONNECTED:
            return "analysis.need_test"
        if self.job is not None and self.job.running:
            return "analysis.running"
        return None

    # ---------------- analysis ----------------
    def confirm(self, title: str, text: str) -> bool:
        """Isolated so tests can answer the dialog."""
        return QMessageBox.question(self, title, text) == QMessageBox.StandardButton.Yes

    def _video_id(self) -> int | None:
        from fortnite_coach.db.models import Video

        with self.ctx.db.session() as s:
            v = s.scalars(select(Video).where(Video.fingerprint == self.current.fingerprint)).first()
            return v.id if v else None

    def start_analysis(self) -> None:
        from fortnite_coach.ai import usage_tracker
        from fortnite_coach.coaching import pipeline
        from fortnite_coach.i18n.translator import get_translator
        from fortnite_coach.workers.analysis_job import AnalysisJob

        if self.analyze_block_reason() is not None:
            return
        self.job_error = None
        self.job_detail = ""
        if process_guard.is_fortnite_running():  # one check, on click only
            self.job_error = "analysis.fortnite_running"
            self.refresh_status()
            return
        settings = self.ctx.settings()
        m = self.current.meta
        req = pipeline.AnalysisRequest(
            video_id=self._video_id(), video_path=m.path, fingerprint=self.current.fingerprint, duration_s=m.duration_s,
            mode=self.selected_mode(), depth=self.selected_depth(), focus=self.selected_focus(),
            language=get_translator().language)
        plan = pipeline.plan(self.ctx.db, settings, req)
        covered = sum(x.length_s for x in plan.segments if x.analyzed)
        est_mb = covered * (2.5 if req.depth.value == "detailed" else 1.5) / 8
        text = tr("analysis.confirm_text", model=settings.gemini.model, requests=plan.to_send, cached=plan.cached,
                  minutes=fmt_duration(covered), mb=f"{est_mb:.0f}" if plan.proxy_needed else "0",
                  used=usage_tracker.requests_today(self.ctx.db), limit=settings.limits.max_requests_per_day)
        if not self.confirm(tr("analysis.confirm_title"), text):
            return
        self.job = AnalysisJob(self.ctx.db, self.ctx.paths, settings, self.ctx.gemini_service(), req)
        self.job.progress.connect(self._on_progress)
        self.job.finished.connect(self._on_done)
        self.job.failed.connect(self._on_failed)
        self.progress_box.show()
        self._on_progress("job.checking", 0, 0)
        self.job.start()
        self.refresh_status()

    def cancel_analysis(self) -> None:
        if self.job is not None and self.job.running:
            self.job.cancel()
            self.progress_label.setText(tr("job.cancelling"))

    def _on_progress(self, step: str, current: int, total: int) -> None:
        self.progress_label.setText(tr(step, i=current, n=total))
        if total:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
        else:
            self.progress_bar.setRange(0, 0)  # busy indicator

    def _on_done(self, outcome) -> None:
        self.progress_box.hide()
        lines = []
        if outcome.reused_report:
            lines.append(tr("result.reused"))
        else:
            if outcome.xp_gained:
                lines.append(tr("result.xp", xp=outcome.xp_gained))
            if outcome.levels_gained:
                lines.append(tr("result.level_up", n=outcome.levels_gained))
            if outcome.xp_skipped_duplicate:
                lines.append(tr("result.xp_duplicate"))
            if outcome.failed_segments:
                lines.append(tr("result.partial", n=outcome.failed_segments))
        banner = "   ·   ".join(lines)
        self.refresh_status()
        self.ctx.open_report(outcome.report_id, banner)
        self.analysis_finished.emit(banner or tr("result.done"))

    def _on_failed(self, err: Exception) -> None:
        from fortnite_coach.core.errors import OperationCancelledError, UsageLimitExceededError

        self.progress_box.hide()
        if isinstance(err, OperationCancelledError):
            self.job_error = "error.cancelled"
        elif isinstance(err, UsageLimitExceededError):
            self.job_error = "error.usage_limit_detail"
            self._limit_params = err.params
        else:
            self.job_error = getattr(err, "i18n_key", "error.generic")
            from fortnite_coach.logging_setup import redact

            self.job_detail = redact(str(err))[:400]
            if self.job_error == "gemini.err_model":  # the tested model stopped working: ask for a new test
                st = self.ctx.settings()
                g = st.gemini.model_copy()
                g.last_test_ok, g.last_test_error, g.last_test_detail = None, None, ""
                st.gemini = g
                self.ctx.save_settings(st)
                win = self.window()
                if hasattr(win, "refresh_gemini_status"):
                    win.refresh_gemini_status()
        self.ctx.data_changed()
        self.refresh_status()

    def _render_coverage(self) -> None:
        if self.current is None:
            self.coverage_label.setText("")
            return
        s = self.ctx.settings()
        segs = plan_segments(self.current.meta.duration_s, s.video.segment_seconds, s.limits.max_video_seconds)
        done, total = coverage(segs)
        skipped = [x for x in segs if not x.analyzed]
        text = tr("analysis.coverage", analyzed=fmt_duration(done), total=fmt_duration(total), n=sum(x.analyzed for x in segs))
        if skipped:
            text += "\n" + tr("analysis.not_covered", start=fmt_duration(skipped[0].start_s), end=fmt_duration(total))
        self.coverage_label.setText(text)

    def _render_video(self) -> None:
        v = self.current
        self.video_card.setVisible(v is not None)
        self.setup_card.setVisible(v is not None)
        if v is None:
            return
        m = v.meta
        self.video_card.set_title(Path(m.path).name, tr("common.measured"))
        for lbl, path in zip(self.thumb_labels, v.thumbnails + [None] * 4):
            pm = QPixmap(str(path)) if path else QPixmap()
            lbl.setPixmap(pm.scaled(lbl.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation) if not pm.isNull() else QPixmap())
        values = {
            "duration": fmt_duration(m.duration_s),
            "resolution": f"{m.width}×{m.height}",
            "fps": f"{m.fps:g}" if m.fps else "?",
            "codec": m.codec.upper(),
            "size": f"{m.size_bytes / 1_048_576:.1f} MB",
            "audio": tr("common.yes") if m.has_audio else tr("common.no"),
        }
        for key, (k, val) in self.meta_labels.items():
            k.setText(tr(f"video.meta.{key}"))
            val.setText(values[key])
        self.open_player_btn.setText(tr("video.open_player"))
        self.open_folder_btn.setText(tr("video.open_folder"))

    def refresh_status(self) -> None:
        reason = self.analyze_block_reason()
        self.analyze_btn.setEnabled(False if reason else True)
        text = tr(reason) if reason else tr("analysis.ready")
        if self.job_error:
            params = getattr(self, "_limit_params", {}) if self.job_error == "error.usage_limit_detail" else {}
            text = "⚠  " + tr(self.job_error, **params) + ("\n" + text if reason else "")
            if getattr(self, "job_detail", ""):
                text += "\n" + tr("gemini.details", text=self.job_detail)
        self.analyze_reason.setText(text)
        self.cancel_btn.setText(tr("common.cancel"))

    def retranslate(self) -> None:
        super().retranslate()
        self._render_recording()
        self._render_import()
        self._render_video()
        self.setup_card.set_title(tr("analysis.setup"), tr("analysis.setup_sub"))
        self.mode_label.setText(tr("analysis.mode"))
        self.depth_label.setText(tr("analysis.depth"))
        self.focus_label.setText(tr("analysis.focus"))
        for i in range(self.mode_combo.count()):
            self.mode_combo.setItemText(i, tr(f"mode.{self.mode_combo.itemData(i)}"))
        for i in range(self.depth_combo.count()):
            d = self.depth_combo.itemData(i)
            self.depth_combo.setItemText(i, f"{tr(f'depth.{d}')} · {tr(f'depth.{d}.desc')}")
        for key, cb in self.focus_boxes.items():
            cb.setText(tr(f"skill.{key}"))
        self.analyze_btn.setText(tr("analysis.analyze"))
        self._render_coverage()
        self.refresh_status()
        self.recent_card.set_title(tr("video.recent"), tr("video.recent_sub"))
        self.recent_empty.set_text(tr("video.recent_empty_title"), tr("video.recent_empty"))
