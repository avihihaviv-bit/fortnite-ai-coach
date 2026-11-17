"""Connection test: lists the models this key can use. Sends no video and no prompt."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from fortnite_coach.ai.gemini_config import ALLOWED_MODELS
from fortnite_coach.ai.gemini_service import GeminiService
from fortnite_coach.core.errors import GeminiError, GeminiNotConfiguredError


@dataclass
class ConnectionTestResult:
    ok: bool
    available_models: list[str] = field(default_factory=list)  # allowed (free-tier) models this key can use
    error_key: str | None = None
    tested_at: str = ""


def test_connection(service: GeminiService) -> ConnectionTestResult:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        names = set(service.list_models())
    except GeminiNotConfiguredError:
        return ConnectionTestResult(False, error_key="gemini.not_configured", tested_at=now)
    except GeminiError as e:
        return ConnectionTestResult(False, error_key=e.i18n_key, tested_at=now)
    usable = [m for m in ALLOWED_MODELS if m in names]
    if not usable:
        return ConnectionTestResult(False, error_key="gemini.err_no_free_model", tested_at=now)
    if service.model not in usable:
        return ConnectionTestResult(False, usable, "gemini.err_model", now)
    return ConnectionTestResult(True, usable, None, now)
