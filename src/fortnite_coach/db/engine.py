"""SQLite engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def create_db_engine(path: Path | str) -> Engine:
    url = "sqlite://" if str(path) == ":memory:" else f"sqlite:///{Path(path).as_posix()}"
    engine = create_engine(url, future=True)

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        if str(path) != ":memory:":
            cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    return engine


class Database:
    """Owns the engine; hands out short-lived ORM sessions."""

    def __init__(self, path: Path | str):
        self.path = path
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_db_engine(path)
        self._factory = sessionmaker(self.engine, expire_on_commit=False)

    def init(self) -> "Database":
        from fortnite_coach.db.migrations import migrate

        migrate(self.engine)
        return self

    @contextmanager
    def session(self) -> Iterator[Session]:
        s = self._factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def close(self) -> None:
        self.engine.dispose()
