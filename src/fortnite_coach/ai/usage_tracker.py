"""Record every Gemini request and enforce the daily limit BEFORE anything is sent."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from fortnite_coach.config.settings import UsageLimits
from fortnite_coach.core.errors import UsageLimitExceededError
from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import ApiUsage

COUNTED_KINDS = ("analysis", "upload")


def record(db: Database, *, model: str, kind: str, success: bool, prompt_tokens: int | None = None,
           output_tokens: int | None = None, error_code: str | None = None, cache_hit: bool = False) -> None:
    with db.session() as s:
        s.add(ApiUsage(model=model, kind=kind, success=success, request_tokens=prompt_tokens,
                       response_tokens=output_tokens, error_code=error_code, cache_hit=cache_hit))


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def requests_today(db: Database) -> int:
    """Requests actually sent to Google today (cache hits are free and not counted)."""
    with db.session() as s:
        return s.scalar(select(func.count(ApiUsage.id)).where(
            ApiUsage.timestamp >= _today_start(), ApiUsage.kind.in_(COUNTED_KINDS),
            ApiUsage.cache_hit.is_(False))) or 0


def tokens_today(db: Database) -> int:
    with db.session() as s:
        return int(s.scalar(select(func.coalesce(func.sum(ApiUsage.request_tokens), 0)
                                   + func.coalesce(func.sum(ApiUsage.response_tokens), 0))
                            .where(ApiUsage.timestamp >= _today_start())) or 0)


def check_budget(db: Database, limits: UsageLimits, planned: int) -> None:
    used = requests_today(db)
    if used + planned > limits.max_requests_per_day:
        raise UsageLimitExceededError(f"{used}+{planned}>{limits.max_requests_per_day}",
                                      used=used, planned=planned, limit=limits.max_requests_per_day)
