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
    detail: str = ""                 # Google's own error text (key redacted), shown to the user


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
    # Listed is not enough: Google lists retired models but refuses them for new keys. Each candidate
    # gets a tiny real request. If the user never chose a model, try the best ones first and keep the
    # first that works; a model the user chose is only tested, never replaced.
    if may_pick:
        candidates = usable
    else:
        candidates = [service.model] if service.model in usable else []
        if not candidates:
            return ConnectionTestResult(False, usable, "gemini.err_model", now)
    from fortnite_coach.logging_setup import redact

    detail = ""
    for model in candidates:
        try:
            service.ping(model)
        except GeminiError as e:
            detail = redact(str(e))[:400]
            if e.i18n_key in ("gemini.err_model", "gemini.err_bad_request", "gemini.err_no_free_quota"):
                continue  # this model is not usable (or not free) for this key: try the next one
            return ConnectionTestResult(False, usable, e.i18n_key, now, detail=detail)
        picked = model if model != service.model else None
        service.model = model
        return ConnectionTestResult(True, usable, None, now, picked_model=picked)
    return ConnectionTestResult(False, usable, "gemini.err_model", now, detail=detail)
