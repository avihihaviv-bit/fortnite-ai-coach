"""Knowledge base access + seeding of the built-in fundamentals pack."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from fortnite_coach.config.paths import resource_path
from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import KnowledgeEntry

BUILTIN_PACK = "knowledge/fundamentals.json"


def load_builtin_pack() -> dict:
    return json.loads(resource_path(BUILTIN_PACK).read_text(encoding="utf-8"))


def seed_builtin(db: Database) -> int:
    """Insert or update built-in entries by key. User/research entries are never touched.
    Returns the number of entries inserted or updated."""
    pack = load_builtin_pack()
    changed = 0
    with db.session() as s:
        existing = {e.key: e for e in s.scalars(select(KnowledgeEntry).where(KnowledgeEntry.key.is_not(None)))}
        for item in pack["entries"]:
            fields = dict(
                topic=item["topic"],
                title=item["title"],
                title_he=item["title_he"],
                content=item["content"],
                kind="fundamental",
                game_version=None,
                source_name=pack["source_name"],
                source_url=None,
                retrieved_at=None,
                is_current=True,
            )
            row = existing.get(item["key"])
            if row is None:
                s.add(KnowledgeEntry(key=item["key"], **fields))
                changed += 1
            elif any(getattr(row, k) != v for k, v in fields.items()):
                for k, v in fields.items():
                    setattr(row, k, v)
                changed += 1
    return changed


def add_researched_entry(
    db: Database, *, topic: str, title: str, content: str, source_name: str, source_url: str,
    retrieved_at: datetime, game_version: str | None,
) -> int:
    """Season-specific facts MUST carry a source and a retrieval date."""
    if not source_name or not source_url or retrieved_at is None:
        raise ValueError("External knowledge requires source_name, source_url and retrieved_at")
    with db.session() as s:
        e = KnowledgeEntry(
            topic=topic, title=title, content=content, kind="season_specific", game_version=game_version,
            source_name=source_name, source_url=source_url, retrieved_at=retrieved_at, is_current=True,
        )
        s.add(e)
        s.flush()
        return e.id


def current_entries(db: Database, topic: str | None = None) -> list[KnowledgeEntry]:
    with db.session() as s:
        q = select(KnowledgeEntry).where(KnowledgeEntry.is_current.is_(True)).order_by(KnowledgeEntry.topic, KnowledgeEntry.id)
        if topic:
            q = q.where(KnowledgeEntry.topic == topic)
        return list(s.scalars(q))


FRESH_DAYS = 60


def season_facts(db: Database, now: datetime | None = None) -> list[KnowledgeEntry]:
    """Current, sourced season facts retrieved within FRESH_DAYS. Older ones never reach the coach."""
    from datetime import timedelta, timezone

    now = now or datetime.now(timezone.utc)
    out = []
    for e in current_entries(db):
        if e.kind != "season_specific" or e.retrieved_at is None:
            continue
        at = e.retrieved_at if e.retrieved_at.tzinfo else e.retrieved_at.replace(tzinfo=timezone.utc)
        if now - at <= timedelta(days=FRESH_DAYS):
            out.append(e)
    return out


def is_stale(e: KnowledgeEntry, now: datetime | None = None) -> bool:
    from datetime import timedelta, timezone

    if e.retrieved_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    at = e.retrieved_at if e.retrieved_at.tzinfo else e.retrieved_at.replace(tzinfo=timezone.utc)
    return now - at > timedelta(days=FRESH_DAYS)
