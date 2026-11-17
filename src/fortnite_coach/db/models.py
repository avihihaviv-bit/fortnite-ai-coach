"""ORM models. Child rows cascade-delete with their parent."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class PlayerProfile(Base):
    __tablename__ = "player_profile"
    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(64), default="")
    input_device: Mapped[str] = mapped_column(String(32), default="keyboard_mouse")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Video(Base):
    """A recording on the user's disk. Only the path is stored - never a copy."""

    __tablename__ = "videos"
    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    duration_s: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    fps: Mapped[float | None] = mapped_column(Float)
    codec: Mapped[str | None] = mapped_column(String(32))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sessions: Mapped[list["Session"]] = relationship(back_populates="video", cascade="all, delete-orphan", passive_deletes=True)


class Session(Base):
    """One analysis request for a video (gameplay or Creative training)."""

    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    game_mode: Mapped[str] = mapped_column(String(32))
    is_training: Mapped[bool] = mapped_column(Boolean, default=False)
    depth: Mapped[str] = mapped_column(String(16))
    focus_skills: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="imported")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    video: Mapped[Video] = relationship(back_populates="sessions")
    report: Mapped["Report | None"] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )


class SessionStatus:
    IMPORTED = "imported"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), unique=True)
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(Text, default="")
    raw_json: Mapped[str] = mapped_column(Text)  # the validated AI response, for audit
    # What was and was not analyzed: [{"start_s", "end_s", "analyzed": bool, "note"}]
    coverage: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    session: Mapped[Session] = relationship(back_populates="report")
    skill_scores: Mapped[list["SkillScore"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    mistakes: Mapped[list["Mistake"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)


class SkillScore(Base):
    __tablename__ = "skill_scores"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    skill: Mapped[str] = mapped_column(String(32), index=True)
    score: Mapped[float | None] = mapped_column(Float)  # None = not enough evidence
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(16), default="ai_estimate")


class Mistake(Base):
    __tablename__ = "mistakes"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    skill: Mapped[str] = mapped_column(String(32))
    code: Mapped[str] = mapped_column(String(64), index=True)  # stable taxonomy code
    severity: Mapped[str] = mapped_column(String(16))
    timestamp_s: Mapped[float | None] = mapped_column(Float)
    timestamp_end_s: Mapped[float | None] = mapped_column(Float)
    what_happened: Mapped[str] = mapped_column(Text)        # what the player did
    better_option: Mapped[str] = mapped_column(Text, default="")  # what would have been better
    why: Mapped[str] = mapped_column(Text, default="")            # why it is better
    how_to_practice: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="")       # what is visible in the video
    confidence: Mapped[float | None] = mapped_column(Float)        # 0..1, from the AI


class TrainingPlan(Base):
    __tablename__ = "training_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    based_on_report_ids: Mapped[list] = mapped_column(JSON, default=list)
    exercises: Mapped[list["Exercise"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="Exercise.order"
    )


class Exercise(Base):
    __tablename__ = "exercises"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(32))  # warm_up, editing, box_fights, ...
    skill: Mapped[str] = mapped_column(String(32))
    goal: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text)
    duration_min: Mapped[int] = mapped_column(Integer)
    difficulty: Mapped[str] = mapped_column(String(16))
    success_criteria: Mapped[str] = mapped_column(Text)
    level_up_when: Mapped[str] = mapped_column(Text, default="")  # when to raise difficulty
    # Map TYPE only (e.g. "edit course"). Map codes are never invented: a code is
    # stored only together with the source it was verified from.
    map_type: Mapped[str] = mapped_column(String(64), default="")
    map_code: Mapped[str | None] = mapped_column(String(32))
    map_code_source: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    source_mistake_codes: Mapped[list] = mapped_column(JSON, default=list)
    order: Mapped[int] = mapped_column(Integer, default=0)
    completions: Mapped[list["ExerciseCompletion"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)


class ExerciseCompletion(Base):
    __tablename__ = "exercise_completions"
    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    minutes: Mapped[int | None] = mapped_column(Integer)
    self_rating: Mapped[int | None] = mapped_column(Integer)  # 1-5, the player's own rating
    notes: Mapped[str] = mapped_column(Text, default="")


class KnowledgeEntry(Base):
    """Updatable Fortnite knowledge. External facts always carry source + date."""

    __tablename__ = "knowledge"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str | None] = mapped_column(String(64), unique=True)  # stable id for built-in packs
    title_he: Mapped[str | None] = mapped_column(String(200))
    topic: Mapped[str] = mapped_column(String(32), index=True)  # building, weapons, meta, ...
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16), default="fundamental")  # fundamental | season_specific
    game_version: Mapped[str | None] = mapped_column(String(32))  # e.g. season/patch, if season-specific
    source_name: Mapped[str | None] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)


class ApiUsage(Base):
    __tablename__ = "api_usage"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    model: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32))  # connection_test | analysis | upload
    request_tokens: Mapped[int | None] = mapped_column(Integer)
    response_tokens: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean)
    error_code: Mapped[str | None] = mapped_column(String(64))
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
