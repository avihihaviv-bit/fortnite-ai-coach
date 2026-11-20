"""Versioned schema migrations.

Each migration is a function that receives a Connection inside a transaction.
Add new migrations to the end of MIGRATIONS; never edit an existing one.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Connection, Engine, text

from fortnite_coach.db.models import Base


def _v1_initial(conn: Connection) -> None:
    Base.metadata.create_all(conn)


def _columns(conn: Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}


def _v2_knowledge_keys(conn: Connection) -> None:
    """Stable keys + Hebrew titles for knowledge entries (databases created by v1)."""
    cols = _columns(conn, "knowledge")
    if "key" not in cols:
        conn.execute(text("ALTER TABLE knowledge ADD COLUMN key VARCHAR(64)"))
    if "title_he" not in cols:
        conn.execute(text("ALTER TABLE knowledge ADD COLUMN title_he VARCHAR(200)"))
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_knowledge_key ON knowledge (key)"))


def _v3_analysis_tables(conn: Connection) -> None:
    """XP events, analysis cache and uploaded-file cache (new tables only; existing data untouched)."""
    from fortnite_coach.db.models import AnalysisCache, GeminiFile, XpEvent

    Base.metadata.create_all(conn, tables=[XpEvent.__table__, AnalysisCache.__table__, GeminiFile.__table__])


def _v4_exercise_template(conn: Connection) -> None:
    if "template_id" not in _columns(conn, "exercises"):
        conn.execute(text("ALTER TABLE exercises ADD COLUMN template_id VARCHAR(64)"))


def _v5_mistake_search_query(conn: Connection) -> None:
    if "search_query" not in _columns(conn, "mistakes"):
        conn.execute(text("ALTER TABLE mistakes ADD COLUMN search_query VARCHAR(120) DEFAULT ''"))


MIGRATIONS: list[tuple[int, Callable[[Connection], None]]] = [
    (1, _v1_initial),
    (2, _v2_knowledge_keys),
    (3, _v3_analysis_tables),
    (4, _v4_exercise_template),
    (5, _v5_mistake_search_query),
]

LATEST_VERSION = MIGRATIONS[-1][0]


def current_version(conn: Connection) -> int:
    conn.execute(text("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"))
    row = conn.execute(text("SELECT MAX(version) FROM schema_version")).scalar()
    return int(row or 0)


def migrate(engine: Engine, migrations: list[tuple[int, Callable[[Connection], None]]] | None = None) -> int:
    """Apply pending migrations. Returns the resulting schema version."""
    migrations = migrations if migrations is not None else MIGRATIONS
    with engine.begin() as conn:
        version = current_version(conn)
    for target, fn in migrations:
        if target <= version:
            continue
        with engine.begin() as conn:  # one transaction per migration
            fn(conn)
            conn.execute(text("INSERT INTO schema_version (version) VALUES (:v)"), {"v": target})
        version = target
    return version
