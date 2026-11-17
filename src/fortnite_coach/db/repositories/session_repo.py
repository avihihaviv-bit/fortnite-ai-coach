"""Videos and analysis sessions."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from fortnite_coach.core.game_modes import AnalysisDepth, GameMode
from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import Report, Session, SessionStatus, Video


@dataclass(frozen=True)
class VideoInfo:
    path: str
    fingerprint: str
    size_bytes: int
    duration_s: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    codec: str | None = None


def upsert_video(db: Database, info: VideoInfo) -> int:
    """Return the id of the video row. The same file (same fingerprint) is never stored twice;
    if it moved on disk, the stored path is updated."""
    with db.session() as s:
        video = s.scalars(select(Video).where(Video.fingerprint == info.fingerprint)).first()
        if video is None:
            video = Video(**info.__dict__)
            s.add(video)
        else:
            video.path = info.path
        s.flush()
        return video.id


def create_session(
    db: Database, video_id: int, mode: GameMode, depth: AnalysisDepth, focus: list[str] | None = None
) -> int:
    with db.session() as s:
        sess = Session(
            video_id=video_id,
            game_mode=mode.value,
            is_training=mode.is_training,
            depth=depth.value,
            focus_skills=list(focus or []),
            status=SessionStatus.IMPORTED,
        )
        s.add(sess)
        s.flush()
        return sess.id


def set_status(db: Database, session_id: int, status: str) -> None:
    with db.session() as s:
        sess = s.get(Session, session_id)
        if sess is not None:
            sess.status = status


def recent_sessions(db: Database, limit: int = 20, *, training: bool | None = None) -> list[Session]:
    with db.session() as s:
        q = (
            select(Session)
            .options(selectinload(Session.video), selectinload(Session.report))
            .order_by(Session.created_at.desc(), Session.id.desc())
            .limit(limit)
        )
        if training is not None:
            q = q.where(Session.is_training == training)
        return list(s.scalars(q))


def delete_session(db: Database, session_id: int) -> bool:
    with db.session() as s:
        sess = s.get(Session, session_id)
        if sess is None:
            return False
        s.delete(sess)
        return True


def counts(db: Database) -> dict[str, int]:
    with db.session() as s:
        return {
            "videos": s.scalar(select(func.count(Video.id))) or 0,
            "sessions": s.scalar(select(func.count(Session.id))) or 0,
            "reports": s.scalar(select(func.count(Report.id))) or 0,
        }
