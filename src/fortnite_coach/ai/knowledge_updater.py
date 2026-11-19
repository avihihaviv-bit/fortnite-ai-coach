"""User-triggered knowledge update via Gemini + Google Search grounding.

Honesty rules:
- One request, only when the user clicks (counts toward the daily limit).
- Sources are NOT taken from the model's text. Each item is kept only if Google's
  grounding metadata shows search results supporting that item's text; the source
  name/link stored are those search results. Items with no support are dropped.
- Every stored fact carries the retrieval date; older season facts are kept as
  history but marked not current.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from pydantic import BaseModel, ValidationError

from fortnite_coach.ai import usage_tracker
from fortnite_coach.ai.gemini_service import GeminiService
from fortnite_coach.config.settings import UsageLimits
from fortnite_coach.core.errors import GeminiError
from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import KnowledgeEntry
from fortnite_coach.db.repositories import knowledge_repo

TOPICS = ("building", "editing", "weapons", "items", "movement", "zone", "ranked", "meta")
MAX_ITEMS = 12

PROMPT = """You are researching the CURRENT Fortnite Battle Royale season for a competitive coaching app.
Use Google Search. Today is {today}.
Find concrete, recent changes that matter for competitive players: building/editing mechanics, weapon classes
and their roles, mobility or healing items, storm/zone behavior, ranked rules, and the current competitive meta.
Rules:
- Only include facts you found in search results during this request. If unsure, leave it out.
- Each item: one short factual statement, no advice, no speculation.
- Name the season/patch version when the source states it.
Return ONLY a JSON array (no markdown, no code fences), at most {max_items} items:
[{{"topic": one of {topics}, "title": "...", "content": "...", "game_version": "... or null"}}]"""


class _Item(BaseModel):
    topic: str
    title: str
    content: str
    game_version: str | None = None


@dataclass
class UpdateResult:
    stored: int = 0
    dropped: int = 0
    deactivated: int = 0
    titles: list[str] = field(default_factory=list)


def _extract_json_array(text: str) -> list:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
    start, end = t.find("["), t.rfind("]")
    if start < 0 or end <= start:
        raise GeminiError("no json array", i18n_key="gemini.err_invalid_response")
    try:
        return json.loads(t[start:end + 1])
    except json.JSONDecodeError as e:
        raise GeminiError(str(e), i18n_key="gemini.err_invalid_response") from e


def _grounding(resp) -> tuple[list[tuple[str, str]], list[tuple[str, list[int]]]]:
    """(chunks [(title, uri)], supports [(segment text, chunk indices)])."""
    cands = getattr(resp, "candidates", None) or []
    meta = getattr(cands[0], "grounding_metadata", None) if cands else None
    if meta is None:
        return [], []
    chunks = []
    for ch in getattr(meta, "grounding_chunks", None) or []:
        web = getattr(ch, "web", None)
        chunks.append((getattr(web, "title", "") or "", getattr(web, "uri", "") or ""))
    supports = []
    for sp in getattr(meta, "grounding_supports", None) or []:
        seg = getattr(sp, "segment", None)
        supports.append((getattr(seg, "text", "") or "", list(getattr(sp, "grounding_chunk_indices", None) or [])))
    return chunks, supports


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def sources_for(item: _Item, chunks, supports) -> list[tuple[str, str]]:
    """Search results whose grounded text overlaps this item's title or content."""
    target = _norm(item.title + " " + item.content)
    found: list[tuple[str, str]] = []
    for text, idxs in supports:
        seg = _norm(text).strip(' ",:[]{}')
        if len(seg) < 12:
            continue
        if seg in target or (len(target) >= 12 and target in seg):
            for i in idxs:
                if 0 <= i < len(chunks) and chunks[i][1] and chunks[i] not in found:
                    found.append(chunks[i])
    return found


def update_knowledge(db: Database, service: GeminiService, limits: UsageLimits) -> UpdateResult:
    from google.genai import types

    usage_tracker.check_budget(db, limits, 1)
    now = datetime.now(timezone.utc)
    config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.1)
    prompt = PROMPT.format(today=f"{now:%Y-%m-%d}", max_items=MAX_ITEMS, topics=list(TOPICS))

    def call():
        return service.client.models.generate_content(model=service.model, contents=prompt, config=config)

    try:
        resp = service._with_retries(call)
    except GeminiError as e:
        usage_tracker.record(db, model=service.model, kind="knowledge", success=False, error_code=e.i18n_key)
        raise
    usage = getattr(resp, "usage_metadata", None)
    usage_tracker.record(db, model=service.model, kind="knowledge", success=True,
                         prompt_tokens=getattr(usage, "prompt_token_count", None),
                         output_tokens=getattr(usage, "candidates_token_count", None))

    chunks, supports = _grounding(resp)
    result = UpdateResult()
    accepted: list[tuple[_Item, list[tuple[str, str]]]] = []
    for raw in _extract_json_array(getattr(resp, "text", ""))[:MAX_ITEMS]:
        try:
            item = _Item.model_validate(raw)
        except ValidationError:
            result.dropped += 1
            continue
        srcs = sources_for(item, chunks, supports)
        if item.topic not in TOPICS or not item.content.strip() or not srcs:
            result.dropped += 1  # no search result supports it -> not stored
            continue
        accepted.append((item, srcs))

    if accepted:  # only replace old facts when there is something verified to replace them with
        with db.session() as s:
            for e in s.query(KnowledgeEntry).filter(KnowledgeEntry.kind == "season_specific",
                                                    KnowledgeEntry.is_current.is_(True)):
                e.is_current = False
                result.deactivated += 1
    for item, srcs in accepted:
        name = ", ".join(t for t, _ in srcs[:3] if t) or "Google Search"
        knowledge_repo.add_researched_entry(db, topic=item.topic, title=item.title.strip()[:200],
                                            content=item.content.strip(), source_name=name[:200],
                                            source_url=srcs[0][1], retrieved_at=now,
                                            game_version=(item.game_version or None))
        result.stored += 1
        result.titles.append(item.title.strip())
    return result
