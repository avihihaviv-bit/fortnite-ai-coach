"""End-to-end pipeline on a real video with a fake Gemini client (TEST DATA responses)."""

import json
import subprocess
import threading

import pytest

from fortnite_coach.ai.gemini_service import GeminiService
from fortnite_coach.coaching.pipeline import AnalysisRequest, plan, run_analysis
from fortnite_coach.config.paths import AppPaths
from fortnite_coach.config.settings import AppSettings
from fortnite_coach.core.errors import GeminiError, OperationCancelledError, UsageLimitExceededError
from fortnite_coach.core.game_modes import AnalysisDepth, GameMode
from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import Report, SessionStatus, Session
from fortnite_coach.db.repositories import report_repo, session_repo
from fortnite_coach.video.importer import import_video
from tests.fake_gemini import FakeAPIError, FakeClient, segment_json


@pytest.fixture(scope="module")
def long_video(tmp_path_factory):
    """TEST DATA: 70 s synthetic video -> 3 segments of 30 s."""
    p = tmp_path_factory.mktemp("pv") / "long.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15:duration=70",
                    "-c:v", "libx264", "-preset", "ultrafast", str(p)], check=True)
    return p


@pytest.fixture
def env(tmp_path, long_video):
    paths = AppPaths(tmp_path / "home").ensure()
    db = Database(paths.database).init()
    iv = import_video(long_video, paths.frames_dir)
    vid = session_repo.upsert_video(db, session_repo.VideoInfo(str(long_video), iv.fingerprint, iv.meta.size_bytes,
                                                               iv.meta.duration_s))
    s = AppSettings()
    s.video.segment_seconds = 30
    req = AnalysisRequest(vid, str(long_video), iv.fingerprint, iv.meta.duration_s, GameMode.BOX_FIGHTS,
                          AnalysisDepth.STANDARD, ["editing"], "en")
    yield db, paths, s, req
    db.close()


def svc(client):
    return GeminiService(lambda: "TEST-KEY", "gemini-2.5-flash", client_factory=lambda k, t: client, sleep=lambda s: None)


def responses():
    return [segment_json("00:05"), segment_json("00:40"), segment_json("01:05")]


def test_full_analysis_stores_report_mistakes_and_xp(env):
    db, paths, s, req = env
    c = FakeClient(responses=responses())
    steps = []
    out = run_analysis(db, paths, s, svc(c), req, progress=lambda k, i, n: steps.append(k))
    assert out.analyzed_segments == 3 and out.failed_segments == 0
    assert c.uploads == 0 and len(c.generate_calls) == 3  # short video: sent inside the request
    assert c.generate_calls[0][1][0].parts[0].inline_data is not None
    assert {"job.preparing", "job.uploading", "job.segment", "job.saving"} <= set(steps)
    d = report_repo.report_detail(db, out.report_id)
    assert len(d.mistakes) == 3 and all(m.how_to_practice and m.evidence for m in d.mistakes)
    assert [round(m.timestamp_s) for m in d.mistakes] == [5, 40, 65]
    assert out.xp_gained == 150 and report_repo.levels(db).overall.total_xp == 150
    assert report_repo.levels(db).skills["editing"].level == 2
    assert out.levels_gained == 1
    # the segment request really carries the segment offsets
    vm = c.generate_calls[1][1][0].parts[0].video_metadata
    assert vm.start_offset == "30.0s" and vm.end_offset == "60.0s" and vm.fps == 1.0


def test_same_video_again_costs_nothing_and_gives_no_xp(env):
    db, paths, s, req = env
    c = FakeClient(responses=responses())
    run_analysis(db, paths, s, svc(c), req)
    out2 = run_analysis(db, paths, s, svc(c), req)
    assert out2.reused_report and c.uploads == 0 and len(c.generate_calls) == 3
    req.depth = AnalysisDepth.DETAILED  # different settings -> new requests, but still no double XP
    c2 = FakeClient(responses=responses())
    out3 = run_analysis(db, paths, s, svc(c2), req)
    assert out3.xp_gained == 0 and out3.xp_skipped_duplicate
    assert report_repo.levels(db).overall.total_xp == 150


def test_partial_failure_is_reported_honestly(env):
    db, paths, s, req = env
    # segment 2 fails both with and without the optional video settings
    c = FakeClient(responses=[segment_json("00:05"), FakeAPIError(400, "bad request"), FakeAPIError(400, "bad request"),
                              segment_json("01:05")])
    out = run_analysis(db, paths, s, svc(c), req)
    assert out.analyzed_segments == 2 and out.failed_segments == 1
    cov = report_repo.report_detail(db, out.report_id).report.coverage
    assert [c["analyzed"] for c in cov] == [True, False, True] and cov[1]["note"] == "gemini.err_bad_request"


def test_bad_key_stops_and_saves_no_report(env):
    db, paths, s, req = env
    c = FakeClient(responses=[FakeAPIError(400, "API key not valid")])
    with pytest.raises(GeminiError):
        run_analysis(db, paths, s, svc(c), req)
    assert len(c.generate_calls) == 1  # fatal: remaining segments not sent
    with db.session() as ss:
        assert ss.query(Report).count() == 0
        assert ss.query(Session).one().status == SessionStatus.FAILED


def test_daily_limit_blocks_before_sending(env):
    db, paths, s, req = env
    s.limits.max_requests_per_day = 2  # needs 1 upload + 3 segments
    c = FakeClient()
    with pytest.raises(UsageLimitExceededError):
        run_analysis(db, paths, s, svc(c), req)
    assert c.uploads == 0 and not c.generate_calls


def test_cancel_leaves_no_report(env):
    db, paths, s, req = env
    cancel = threading.Event()
    c = FakeClient()

    def progress(step, i, n):
        if step == "job.segment" and i == 2:
            cancel.set()

    with pytest.raises(OperationCancelledError):
        run_analysis(db, paths, s, svc(c), req, progress=progress, cancel=cancel)
    with db.session() as ss:
        assert ss.query(Report).count() == 0
        assert ss.query(Session).one().status == SessionStatus.CANCELLED


def test_over_limit_part_is_marked_not_analyzed(env):
    db, paths, s, req = env
    s.limits.max_video_seconds = 60
    p = plan(db, s, req)
    assert [x.analyzed for x in p.segments] == [True, True, False]
    out = run_analysis(db, paths, s, svc(FakeClient(responses=responses())), req)
    cov = report_repo.report_detail(db, out.report_id).report.coverage
    assert cov[2] == {**cov[2], "analyzed": False, "note": "over_limit"}


def test_deleting_session_removes_its_xp(env):
    db, paths, s, req = env
    out = run_analysis(db, paths, s, svc(FakeClient(responses=responses())), req)
    assert report_repo.levels(db).overall.total_xp == 150
    session_repo.delete_session(db, out.session_id)
    assert report_repo.levels(db).overall.total_xp == 0


def test_prompt_contains_rules_and_codes(env):
    db, paths, s, req = env
    c = FakeClient(responses=responses())
    run_analysis(db, paths, s, svc(c), req)
    system = c.generate_calls[0][2].system_instruction
    for needle in ("Never invent", "not_determinable", "EDIT_EXPOSED_AFTER", "EDIT_HARD_FAST", "sensitivity", "box_fights"):
        assert needle in system


def test_bad_request_retries_without_optional_video_settings(env):
    db, paths, s, req = env
    c = FakeClient(responses=[FakeAPIError(400, "Invalid value at 'media_resolution'"), segment_json("00:05"),
                              segment_json("00:40"), segment_json("01:05")])
    out = run_analysis(db, paths, s, svc(c), req)
    assert out.analyzed_segments == 3 and out.failed_segments == 0
    first, retry = c.generate_calls[0], c.generate_calls[1]
    assert first[2].media_resolution is not None and first[1][0].parts[0].video_metadata.fps == 1.0
    assert retry[2].media_resolution is None and retry[1][0].parts[0].video_metadata.fps is None


def test_invalid_json_is_retried_once(env):
    db, paths, s, req = env
    c = FakeClient(responses=["{not json", segment_json("00:05"), segment_json("00:40"), segment_json("01:05")])
    out = run_analysis(db, paths, s, svc(c), req)
    assert out.analyzed_segments == 3 and len(c.generate_calls) == 4


def test_large_video_uses_files_api(env, monkeypatch):
    from fortnite_coach.coaching import pipeline

    monkeypatch.setattr(pipeline, "INLINE_MAX_MB", 0.0)
    db, paths, s, req = env
    c = FakeClient(responses=responses())
    run_analysis(db, paths, s, svc(c), req)
    assert c.uploads == 1 and c.generate_calls[0][1][0].parts[0].file_data is not None


def test_missing_uploaded_file_falls_back_to_inline(env, monkeypatch):
    """Files API upload 'not found' at analysis time: resend the video inside the request."""
    from fortnite_coach.coaching import pipeline

    db, paths, s, req = env
    monkeypatch.setattr(pipeline, "INLINE_MAX_MB", 0.0)
    c = FakeClient(responses=[FakeAPIError(404, "Requested entity was not found."), *responses()])
    orig_upload = pipeline._upload

    def upload_then_allow_inline(*a, **k):
        f = orig_upload(*a, **k)
        monkeypatch.setattr(pipeline, "INLINE_MAX_MB", 14.0)  # the proxy is small enough to inline
        return f

    monkeypatch.setattr(pipeline, "_upload", upload_then_allow_inline)
    out = run_analysis(db, paths, s, svc(c), req)
    assert out.analyzed_segments == 3 and out.failed_segments == 0
    assert c.generate_calls[1][1][0].parts[0].inline_data is not None


def test_failure_keeps_googles_own_message(env):
    db, paths, s, req = env
    c = FakeClient(responses=[FakeAPIError(400, "API key not valid. Please pass a valid API key. TEST DATA")])
    with pytest.raises(GeminiError) as e:
        run_analysis(db, paths, s, svc(c), req)
    assert "API key not valid" in str(e.value) and "no segment analyzed" not in str(e.value)
