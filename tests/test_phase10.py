"""Phase 10: usage summary, sourced knowledge updates, remote file deletion, privacy/security checks. TEST DATA only."""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from fortnite_coach.ai import request_cache, usage_tracker
from fortnite_coach.ai.gemini_service import GeminiService
from fortnite_coach.ai.knowledge_updater import update_knowledge
from fortnite_coach.coaching.prompt_builder import system_instruction
from fortnite_coach.config.settings import UsageLimits
from fortnite_coach.core.errors import UsageLimitExceededError
from fortnite_coach.core.game_modes import GameMode
from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import GeminiFile, KnowledgeEntry
from fortnite_coach.db.repositories import data_repo, knowledge_repo
from tests.fake_gemini import FakeClient

ROOT = Path(__file__).resolve().parents[1]


def svc(client):
    return GeminiService(lambda: "TEST-KEY", "gemini-2.5-flash", client_factory=lambda k, t: client, sleep=lambda s: None)


# ---------------------------------------------------------------- usage
def test_usage_summary_counts(tmp_path):
    db = Database(tmp_path / "c.db").init()
    usage_tracker.record(db, model="m", kind="analysis", success=True, prompt_tokens=100, output_tokens=20)
    usage_tracker.record(db, model="m", kind="upload", success=True)
    usage_tracker.record(db, model="m", kind="analysis", success=True, cache_hit=True)
    usage_tracker.record(db, model="m", kind="analysis", success=False, error_code="gemini.err_rate_limit")
    usage_tracker.record(db, model="m", kind="connection_test", success=True)
    s = usage_tracker.summary(db, 1)
    assert (s.sent, s.cache_hits, s.connection_tests, s.tokens_in, s.tokens_out) == (3, 1, 1, 100, 20)
    assert s.failures["gemini.err_rate_limit"] == 1 and s.per_day[0][1:] == (3, 1, 1)
    assert usage_tracker.requests_today(db) == 3


def test_clear_result_cache(tmp_path):
    db = Database(tmp_path / "c.db").init()
    request_cache.put(db, "k1", "{}")
    assert request_cache.count(db) == 1 and request_cache.clear(db) == 1 and request_cache.count(db) == 0


# ---------------------------------------------------------------- knowledge
ITEMS = [  # TEST DATA
    {"topic": "weapons", "title": "TEST DATA shotgun change", "content": "TEST DATA the pump shotgun was vaulted this season",
     "game_version": "TEST 1.0"},
    {"topic": "zone", "title": "TEST DATA invented fact", "content": "TEST DATA a claim no search result supports", "game_version": None},
    {"topic": "nonsense", "title": "x", "content": "TEST DATA bad topic"},
]


def grounded_response(items=ITEMS):
    text = json.dumps(items)
    meta = SimpleNamespace(
        grounding_chunks=[SimpleNamespace(web=SimpleNamespace(uri="https://example.invalid/patch-notes", title="example.invalid"))],
        grounding_supports=[SimpleNamespace(segment=SimpleNamespace(text="TEST DATA the pump shotgun was vaulted this season"),
                                            grounding_chunk_indices=[0])])
    return SimpleNamespace(text=text, candidates=[SimpleNamespace(grounding_metadata=meta)],
                           usage_metadata=SimpleNamespace(prompt_token_count=50, candidates_token_count=80))


class KnowledgeClient(FakeClient):
    def __init__(self, resp):
        super().__init__()
        self.resp = resp

    def _generate(self, model, contents, config):
        self.generate_calls.append((model, contents, config))
        return self.resp


def test_only_search_backed_facts_are_stored(tmp_path):
    db = Database(tmp_path / "c.db").init()
    client = KnowledgeClient(grounded_response())
    res = update_knowledge(db, svc(client), UsageLimits())
    assert res.stored == 1 and res.dropped == 2
    tool = client.generate_calls[0][2].tools[0]
    assert tool.google_search is not None  # grounded request
    facts = knowledge_repo.season_facts(db)
    assert len(facts) == 1
    f = facts[0]
    assert f.source_url == "https://example.invalid/patch-notes" and f.source_name == "example.invalid"
    assert f.retrieved_at is not None and f.game_version == "TEST 1.0"
    assert usage_tracker.requests_today(db) == 1


def test_update_replaces_old_facts_but_keeps_history(tmp_path):
    db = Database(tmp_path / "c.db").init()
    update_knowledge(db, svc(KnowledgeClient(grounded_response())), UsageLimits())
    update_knowledge(db, svc(KnowledgeClient(grounded_response())), UsageLimits())
    with db.session() as s:
        rows = s.query(KnowledgeEntry).filter_by(kind="season_specific").all()
    assert len(rows) == 2 and sum(r.is_current for r in rows) == 1


def test_nothing_verified_keeps_previous_facts(tmp_path):
    db = Database(tmp_path / "c.db").init()
    update_knowledge(db, svc(KnowledgeClient(grounded_response())), UsageLimits())
    empty = grounded_response([ITEMS[1]])
    res = update_knowledge(db, svc(KnowledgeClient(empty)), UsageLimits())
    assert res.stored == 0 and len(knowledge_repo.season_facts(db)) == 1


def test_knowledge_update_respects_daily_limit(tmp_path):
    db = Database(tmp_path / "c.db").init()
    client = KnowledgeClient(grounded_response())
    with pytest.raises(UsageLimitExceededError):
        update_knowledge(db, svc(client), UsageLimits(max_requests_per_day=0))
    assert not client.generate_calls


def test_stale_facts_never_reach_the_coach(tmp_path):
    db = Database(tmp_path / "c.db").init()
    old = datetime.now(timezone.utc) - timedelta(days=knowledge_repo.FRESH_DAYS + 5)
    knowledge_repo.add_researched_entry(db, topic="meta", title="TEST DATA old", content="TEST DATA old meta",
                                        source_name="s", source_url="https://example.invalid", retrieved_at=old,
                                        game_version=None)
    assert knowledge_repo.season_facts(db) == []
    fresh = [("TEST DATA t", "TEST DATA c", "2026-11-19", "example.invalid")]
    text = system_instruction(GameMode.BOX_FIGHTS, ["editing"], "en", [], fresh)
    assert "as of 2026-11-19, source: example.invalid" in text


# ---------------------------------------------------------------- deletion / security
def test_delete_uploaded_files(tmp_path):
    db = Database(tmp_path / "c.db").init()
    with db.session() as s:
        s.add(GeminiFile(proxy_key="p1", name="files/a", uri="u", mime_type="video/mp4"))
        s.add(GeminiFile(proxy_key="p2", name="files/b", uri="u", mime_type="video/mp4"))
    deleted = []
    client = FakeClient()
    client.files.delete = lambda name: deleted.append(name)
    assert data_repo.delete_uploaded_files(db, svc(client)) == (2, 0)
    assert deleted == ["files/a", "files/b"] and data_repo.uploaded_file_names(db) == []


def test_requirements_have_major_upper_bounds():
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            assert "<" in line, line


def test_gitignore_protects_secrets_and_user_data():
    gi = (ROOT / ".gitignore").read_text()
    for pattern in (".env", "*.db", "*.mp4", "dist/", "vendor/ffmpeg/", "*.key"):
        assert pattern in gi, pattern


def test_repository_contains_no_api_key():
    pattern = re.compile(r"AIza[0-9A-Za-z_\-]{35}")
    for f in ROOT.rglob("*"):
        if f.is_file() and ".git" not in f.parts and "tests" not in f.parts and f.suffix in (".py", ".json", ".md", ".txt", ".toml", ".yml", ".iss", ".bat", ".ps1"):
            assert not pattern.search(f.read_text(encoding="utf-8", errors="ignore")), f


def test_privacy_and_live_coach_docs_bundled():
    spec = (ROOT / "packaging" / "fortnite_coach.spec").read_text()
    for doc in ("PRIVACY.md", "LIVE_COACH.md"):
        assert (ROOT / "docs" / doc).is_file() and doc in spec
