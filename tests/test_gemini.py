"""Gemini layer with a fake client. No key, no network. All AI responses are TEST DATA."""

import json

import pytest

from fortnite_coach.ai import request_cache, usage_tracker
from fortnite_coach.ai.gemini_connection_test import test_connection as run_connection_test
from fortnite_coach.ai.gemini_response_parser import load_segment_result, parse_timestamp, validate_segment
from fortnite_coach.ai.gemini_service import GeminiService, classify
from fortnite_coach.ai.schemas import SegmentResult
from fortnite_coach.config.settings import UsageLimits
from fortnite_coach.core.errors import GeminiError, GeminiNotConfiguredError, UsageLimitExceededError
from fortnite_coach.db.engine import Database
from tests.fake_gemini import FakeAPIError, FakeClient, segment_json


def service(client, key="TEST-KEY", model="gemini-2.5-flash", sleeps=None):
    return GeminiService(lambda: key, model, client_factory=lambda k, t: client,
                         sleep=(sleeps.append if sleeps is not None else (lambda s: None)))


def test_no_key_never_creates_client():
    s = GeminiService(lambda: None, "gemini-2.5-flash", client_factory=lambda k, t: pytest.fail("created"))
    with pytest.raises(GeminiNotConfiguredError):
        s.list_models()


def test_classification():
    assert classify(FakeAPIError(429, "RESOURCE_EXHAUSTED retryDelay: 7s")).retryable
    assert classify(FakeAPIError(429, "RESOURCE_EXHAUSTED retryDelay: 7s")).delay_s == 7
    assert classify(FakeAPIError(429, "Quota exceeded GenerateRequestsPerDayPerProjectPerModel")).i18n_key == "gemini.err_quota_daily"
    assert classify(FakeAPIError(400, "API key not valid")).i18n_key == "gemini.err_key"
    assert not classify(FakeAPIError(403, "PERMISSION_DENIED")).retryable
    assert classify(FakeAPIError(503, "UNAVAILABLE")).retryable
    assert classify(TimeoutError("timed out")).i18n_key == "gemini.err_network"


def test_retry_then_success_honors_delay():
    sleeps = []
    c = FakeClient(responses=[FakeAPIError(429, "RESOURCE_EXHAUSTED retryDelay: 5s"), segment_json()])
    s = service(c, sleeps=sleeps)
    from fortnite_coach.ai.gemini_service import UploadedFile

    res = s.generate_segment(UploadedFile("f", "u", "video/mp4"), 0, 10, 1, True, "sys", "p", SegmentResult)
    assert json.loads(res.text)["segment_summary"] and sleeps == [5.0] and len(c.generate_calls) == 2


def test_no_retry_on_bad_key():
    c = FakeClient(responses=[FakeAPIError(400, "API key not valid. Please pass a valid API key.")])
    from fortnite_coach.ai.gemini_service import UploadedFile

    with pytest.raises(GeminiError) as e:
        service(c).generate_segment(UploadedFile("f", "u", "video/mp4"), 0, 10, 1, True, "s", "p", SegmentResult)
    assert e.value.i18n_key == "gemini.err_key" and len(c.generate_calls) == 1


def test_upload_waits_until_active():
    c = FakeClient()
    f = service(c).upload_video("x.mp4", "video/mp4")
    assert f.uri.endswith("test-1") and c.uploads == 1


def test_connection_test_results():
    assert run_connection_test(service(FakeClient())).ok
    r = run_connection_test(service(FakeClient(models=("gemini-2.5-flash-lite",))))
    assert not r.ok and r.error_key == "gemini.err_model" and r.available_models == ["gemini-2.5-flash-lite"]
    r = run_connection_test(service(FakeClient(models=("gemini-9-ultra-paid",))))
    assert r.error_key == "gemini.err_no_free_model"
    r = run_connection_test(service(FakeClient(list_error=FakeAPIError(400, "API key not valid"))))
    assert not r.ok and r.error_key == "gemini.err_key"


def test_parser_validates_and_drops_unsupported_items():
    assert parse_timestamp("02:14") == 134 and parse_timestamp("1:02:03") == 3723 and parse_timestamp("bad") is None
    data = json.loads(segment_json(start="00:05"))
    data["mistakes"].append({**data["mistakes"][0], "start": "09:00", "end": "09:01"})  # outside the segment
    data["mistakes"].append({**data["mistakes"][0], "evidence": ""})                    # no evidence
    data["skill_assessments"].append({"skill": "aim", "score": 90, "evidence_count": 0, "confidence": 1, "rationale": ""})
    seg = validate_segment(SegmentResult.model_validate(data), 0, 0, 60)
    assert len(seg.mistakes) == 1 and seg.dropped == 2
    assert seg.mistakes[0].start_s == 5 and seg.mistakes[0].how_to_practice
    aim = [a for a in seg.assessments if a.skill == "aim"][0]
    assert aim.score is None  # a score without evidence is never kept
    assert seg.good_plays[0].difficulty == "hard"


def test_invalid_json_rejected():
    with pytest.raises(GeminiError) as e:
        load_segment_result("not json")
    assert e.value.i18n_key == "gemini.err_invalid_response"


def test_usage_limit_hard_stop(tmp_path):
    db = Database(tmp_path / "c.db").init()
    lim = UsageLimits(max_requests_per_day=3)
    usage_tracker.check_budget(db, lim, 3)
    for _ in range(2):
        usage_tracker.record(db, model="m", kind="analysis", success=True)
    usage_tracker.record(db, model="m", kind="analysis", success=True, cache_hit=True)  # free, not counted
    assert usage_tracker.requests_today(db) == 2
    with pytest.raises(UsageLimitExceededError):
        usage_tracker.check_budget(db, lim, 2)


def test_request_cache(tmp_path):
    db = Database(tmp_path / "c.db").init()
    k = request_cache.make_key(fp="a", seg=1)
    assert request_cache.get(db, k) is None
    request_cache.put(db, k, "{}")
    assert request_cache.get(db, k) == "{}" and request_cache.make_key(fp="a", seg=2) != k


def test_flash_discovery_and_ranking():
    from fortnite_coach.ai.gemini_config import usable_models

    names = ["gemini-2.5-flash", "gemini-3-flash", "gemini-3-flash-lite", "gemini-3-pro", "gemini-2.5-flash-preview-tts",
             "gemini-3-flash-image", "gemini-3.1-flash-preview", "text-embedding-004", "gemini-2.5-flash-live"]
    assert usable_models(names) == ["gemini-3-flash", "gemini-3-flash-lite", "gemini-2.5-flash", "gemini-3.1-flash-preview"]


def test_retired_default_is_replaced_only_if_user_never_chose():
    newer = FakeClient(models=("gemini-3-flash", "gemini-3-flash-lite"))  # TEST DATA: 2.5 retired
    r = run_connection_test(service(newer), may_pick=True)
    assert r.ok and r.picked_model == "gemini-3-flash"
    r = run_connection_test(service(FakeClient(models=("gemini-3-flash",))), may_pick=False)
    assert not r.ok and r.error_key == "gemini.err_model" and r.available_models == ["gemini-3-flash"]


def test_listed_but_retired_model_is_skipped_by_real_ping():
    """Google lists gemini-2.5-flash but refuses it for new keys: the test must find a model that works."""
    c = FakeClient(models=("gemini-2.5-flash", "gemini-3-flash"), blocked_models={"gemini-3-flash"})
    r = run_connection_test(service(c), may_pick=True)
    assert r.ok and r.picked_model is None and c.pings == ["gemini-2.5-flash"]  # 3 blocked -> next one works
    c = FakeClient(models=("gemini-2.5-flash", "gemini-2.5-flash-lite"), blocked_models={"gemini-2.5-flash"})
    r = run_connection_test(service(c), may_pick=True)
    assert r.ok and r.picked_model == "gemini-2.5-flash-lite"


def test_chosen_model_that_is_blocked_reports_google_text():
    c = FakeClient(models=("gemini-2.5-flash",), blocked_models={"gemini-2.5-flash"})
    r = run_connection_test(service(c), may_pick=False)
    assert not r.ok and r.error_key == "gemini.err_model" and "no longer available to new users" in r.detail


def test_file_not_found_is_not_reported_as_model_problem():
    assert classify(FakeAPIError(404, "File files/abc is not found or not accessible")).i18n_key == "gemini.err_file"
    assert classify(FakeAPIError(404, "models/gemini-x is not found for API version v1beta")).i18n_key == "gemini.err_model"
