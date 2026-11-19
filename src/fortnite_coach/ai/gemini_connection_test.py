"""Connection test: lists the models this key can use. Sends no video and no prompt."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from fortnite_coach.ai.gemini_config import usable_models
from fortnite_coach.ai.gemini_service import GeminiService
from fortnite_coach.core.errors import GeminiError, GeminiNotConfiguredError


@dataclass
class ConnectionTestResult:
    ok: bool
    available_models: list[str] = field(default_factory=list)  # allowed (free-tier) models this key can use
    error_key: str | None = None
    tested_at: str = ""
    picked_model: str | None = None  # set when the app chose a model because the user never picked one


def test_connection(service: GeminiService, *, may_pick: bool = False) -> ConnectionTestResult:
    """may_pick: the user never chose a model, so if the default is retired the best available Flash
    model is selected (and shown to the user). A model the user chose is never replaced."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        names = set(service.list_models())
    except GeminiNotConfiguredError:
        return ConnectionTestResult(False, error_key="gemini.not_configured", tested_at=now)
    except GeminiError as e:
        return ConnectionTestResult(False, error_key=e.i18n_key, tested_at=now)
    usable = usable_models(names)
    if not usable:
        return ConnectionTestResult(False, error_key="gemini.err_no_free_model", tested_at=now)
    if service.model not in usable:
        if may_pick:
            service.model = usable[0]
            return ConnectionTestResult(True, usable, None, now, picked_model=usable[0])
        return ConnectionTestResult(False, usable, "gemini.err_model", now)
    return ConnectionTestResult(True, usable, None, now)
