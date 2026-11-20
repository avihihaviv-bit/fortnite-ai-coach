"""The analysis pipeline. Runs on a worker thread, only after the user confirmed.

plan segments -> usage check -> cached results? -> analysis copy -> upload (or reuse)
-> one request per uncached segment -> validate -> merge -> save report + mistakes + XP.

Honesty rules enforced here:
- Segments that fail are recorded as "not analyzed" in the coverage, never filled in.
- If no segment succeeds, no report is saved.
- Cancel stops between steps; a cancelled session has no report.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from fortnite_coach.ai import request_cache, usage_tracker
from fortnite_coach.ai.gemini_config import DEPTH_PROFILES, PROMPT_VERSION
from fortnite_coach.ai.gemini_response_parser import ParsedSegment, load_segment_result, validate_segment
from fortnite_coach.ai.gemini_service import GeminiService, UploadedFile
from fortnite_coach.ai.schemas import SegmentResult
from fortnite_coach.coaching.aggregate import aggregate
from fortnite_coach.coaching.levels import level_from_xp
from fortnite_coach.coaching.prompt_builder import segment_prompt, system_instruction
from fortnite_coach.config.paths import AppPaths
from fortnite_coach.config.settings import AppSettings
from fortnite_coach.core.errors import CoachError, GeminiError, OperationCancelledError, VideoError
from fortnite_coach.core.game_modes import AnalysisDepth, GameMode
from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import GeminiFile, SessionStatus
from fortnite_coach.db.repositories import knowledge_repo, report_repo, session_repo
from fortnite_coach.video.ffmpeg_tools import find_ffmpeg
from fortnite_coach.video.proxy import make_proxy, proxy_path
from fortnite_coach.video.segments import Segment, plan_segments

log = logging.getLogger(__name__)
FATAL_KEYS = {"gemini.err_key", "gemini.err_quota_daily", "gemini.err_model", "gemini.not_configured",
              "gemini.err_no_free_quota", "gemini.err_region", "gemini.err_file"}

ProgressFn = Callable[[str, int, int], None]  # (i18n step key, current, total)


@dataclass
class AnalysisRequest:
    video_id: int
    video_path: str
    fingerprint: str
    duration_s: float
    mode: GameMode
    depth: AnalysisDepth
    focus: list[str]
    language: str


@dataclass
class AnalysisPlan:
    segments: list[Segment]
    to_send: int            # requests that will actually be sent (not cached)
    cached: int
    proxy_needed: bool


@dataclass
class AnalysisOutcome:
    session_id: int
    report_id: int | None
    analyzed_segments: int
    failed_segments: int
    xp_gained: int = 0
    xp_skipped_duplicate: bool = False
    levels_gained: int = 0
    errors: list[str] = field(default_factory=list)
    reused_report: bool = False


def _cache_key(req: AnalysisRequest, seg: Segment, model: str) -> str:
    return request_cache.make_key(fp=req.fingerprint, start=seg.start_s, end=seg.end_s, depth=req.depth.value,
                                  focus=sorted(req.focus), mode=req.mode.value, model=model, lang=req.language,
                                  prompt=PROMPT_VERSION)


def plan(db: Database, settings: AppSettings, req: AnalysisRequest) -> AnalysisPlan:
    segs = plan_segments(req.duration_s, settings.video.segment_seconds, settings.limits.max_video_seconds)
    analyzed = [s for s in segs if s.analyzed]
    cached = sum(1 for s in analyzed if request_cache.get(db, _cache_key(req, s, settings.gemini.model)))
    to_send = len(analyzed) - cached
    return AnalysisPlan(segs, to_send, cached, proxy_needed=to_send > 0)


def _upload(db: Database, service: GeminiService, proxy: Path, key: str, cancel) -> UploadedFile:
    with db.session() as s:
        row = s.query(GeminiFile).filter_by(proxy_key=key).first()
        known = UploadedFile(row.name, row.uri, row.mime_type) if row else None
    if known and service.file_is_active(known.name):
        return known  # Google still has it (files live ~48 h): no second upload
    f = service.upload_video(proxy, "video/mp4", cancel)
    usage_tracker.record(db, model=service.model, kind="upload", success=True)
    with db.session() as s:
        row = s.query(GeminiFile).filter_by(proxy_key=key).first()
        if row is None:
            s.add(GeminiFile(proxy_key=key, name=f.name, uri=f.uri, mime_type=f.mime_type))
        else:
            row.name, row.uri, row.mime_type = f.name, f.uri, f.mime_type
    return f


def run_analysis(
    db: Database, paths: AppPaths, settings: AppSettings, service: GeminiService, req: AnalysisRequest,
    progress: ProgressFn = lambda *_: None, cancel: threading.Event | None = None,
) -> AnalysisOutcome:
    cancel = cancel or threading.Event()
    model = settings.gemini.model
    profile = DEPTH_PROFILES[req.depth]

    def check_cancel():
        if cancel.is_set():
            raise OperationCancelledError()

    progress("job.checking", 0, 0)
    p = plan(db, settings, req)
    analyzed_segs = [s for s in p.segments if s.analyzed]
    if not analyzed_segs:
        raise VideoError("nothing to analyze", i18n_key="video.err_unreadable")
    if p.to_send == 0:
        existing = report_repo.find_report(db, req.fingerprint, req.mode.value, req.depth.value, req.focus)
        if existing is not None:  # identical analysis already in history: show it, send nothing
            return AnalysisOutcome(session_id=0, report_id=existing, analyzed_segments=0, failed_segments=0,
                                   reused_report=True)
    usage_tracker.check_budget(db, settings.limits, p.to_send + (1 if p.proxy_needed else 0))

    session_id = session_repo.create_session(db, req.video_id, req.mode, req.depth, req.focus)
    session_repo.set_status(db, session_id, SessionStatus.ANALYZING)
    outcome = AnalysisOutcome(session_id, None, 0, 0)
    try:
        uploaded: UploadedFile | None = None
        if p.proxy_needed:
            check_cancel()
            progress("job.preparing", 0, 0)
            covered_s = analyzed_segs[-1].end_s
            out = proxy_path(paths.clips_dir, req.fingerprint, profile.proxy_height, covered_s)
            proxy = make_proxy(find_ffmpeg(settings.ffmpeg_path), Path(req.video_path), out,
                               height=profile.proxy_height, max_seconds=covered_s, cancel=cancel)
            size_mb = proxy.stat().st_size / 1_048_576
            if size_mb > settings.limits.max_upload_mb:
                raise VideoError(f"{size_mb:.0f} MB", i18n_key="video.err_too_big")
            check_cancel()
            progress("job.uploading", 0, 0)
            uploaded = _upload(db, service, proxy, out.name, cancel)

        knowledge = [(e.title, e.content) for e in knowledge_repo.current_entries(db) if e.kind == "fundamental"]
        season = [(e.title, e.content, f"{e.retrieved_at:%Y-%m-%d}", e.source_name or "")
                  for e in knowledge_repo.season_facts(db)]
        system = system_instruction(req.mode, req.focus, req.language, knowledge, season)
        parsed: list[ParsedSegment] = []
        raw: list[dict] = []
        coverage: list[dict] = []
        fatal: str | None = None
        for i, seg in enumerate(p.segments):
            entry = {"index": seg.index, "start_s": seg.start_s, "end_s": seg.end_s, "analyzed": False, "note": ""}
            coverage.append(entry)
            if not seg.analyzed:
                entry["note"] = "over_limit"
                continue
            if fatal:
                entry["note"] = fatal
                outcome.failed_segments += 1
                continue
            check_cancel()
            progress("job.segment", i + 1, len(analyzed_segs))
            key = _cache_key(req, seg, model)
            text = request_cache.get(db, key)
            from_cache = text is not None
            try:
                def ask():
                    res = service.generate_segment(uploaded, seg.start_s, seg.end_s, profile.fps, profile.low_resolution,
                                                   system, segment_prompt(seg.start_s, seg.end_s, i, len(analyzed_segs)),
                                                   SegmentResult, cancel)
                    usage_tracker.record(db, model=model, kind="analysis", success=True,
                                         prompt_tokens=res.prompt_tokens, output_tokens=res.output_tokens)
                    return res.text

                if not from_cache:
                    text = ask()
                try:
                    result = load_segment_result(text)
                except GeminiError:
                    if from_cache:
                        raise
                    # One retry when the answer is not valid JSON (rare, but happens with long answers).
                    usage_tracker.check_budget(db, settings.limits, 1)
                    text = ask()
                    result = load_segment_result(text)
                if not from_cache:
                    request_cache.put(db, key, text)
                else:
                    usage_tracker.record(db, model=model, kind="analysis", success=True, cache_hit=True)
                parsed.append(validate_segment(result, seg.index, seg.start_s, seg.end_s))
                raw.append(json.loads(text))
                entry["analyzed"] = True
                outcome.analyzed_segments += 1
            except OperationCancelledError:
                raise
            except GeminiError as e:
                usage_tracker.record(db, model=model, kind="analysis", success=False, error_code=e.i18n_key)
                entry["note"] = e.i18n_key
                outcome.failed_segments += 1
                outcome.errors.append(e.i18n_key)
                if e.i18n_key in FATAL_KEYS:
                    fatal = e.i18n_key

        if not parsed:
            session_repo.set_status(db, session_id, SessionStatus.FAILED)
            raise GeminiError("no segment analyzed", i18n_key=outcome.errors[0] if outcome.errors else "error.gemini")

        progress("job.saving", 0, 0)
        agg = aggregate(parsed)
        before = sum(report_repo.xp_totals(db).values())
        award = not report_repo.xp_already_awarded(db, req.fingerprint)
        outcome.report_id = report_repo.save_report(db, session_id, model=model, prompt_version=PROMPT_VERSION,
                                                    agg=agg, coverage=coverage, raw=raw, award_xp=award)
        outcome.xp_skipped_duplicate = not award and bool(agg.xp)
        outcome.xp_gained = sum(x.amount for x in agg.xp) if award else 0
        outcome.levels_gained = level_from_xp(before + outcome.xp_gained).level - level_from_xp(before).level
        from fortnite_coach.coaching.training_plan import generate_plan

        generate_plan(db)  # the plan always follows the latest evidence
        return outcome
    except OperationCancelledError:
        session_repo.set_status(db, session_id, SessionStatus.CANCELLED)
        raise
    except CoachError:
        if outcome.report_id is None:
            session_repo.set_status(db, session_id, SessionStatus.FAILED)
        raise
