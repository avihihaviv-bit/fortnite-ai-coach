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


REQUEST_TIMEOUT_S = 25   # one test request; the big video timeout is only for analysis
TOTAL_DEADLINE_S = 75    # the whole test, so "Testing..." never hangs
MAX_CANDIDATES = 4


def test_connection(service: GeminiService, *, may_pick: bool = False) -> ConnectionTestResult:
    """may_pick: the user never chose a model, so if the default is retired the best available Flash
    model is selected (and shown to the user). A model the user chose is never replaced."""
    import time

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    start = time.monotonic()
    service.max_retries = min(service.max_retries, 1)  # a test should answer fast, not retry for minutes
    try:
        names = set(service.list_models(timeout_s=REQUEST_TIMEOUT_S))
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
        candidates = usable[:MAX_CANDIDATES]
    else:
        candidates = [service.model] if service.model in usable else []
        if not candidates:
            return ConnectionTestResult(False, usable, "gemini.err_model", now)
    from fortnite_coach.logging_setup import redact

    detail = ""
    for model in candidates:
        if time.monotonic() - start > TOTAL_DEADLINE_S:
            return ConnectionTestResult(False, usable, "gemini.err_test_timeout", now, detail=detail)
        try:
            service.ping(model, timeout_s=REQUEST_TIMEOUT_S)
        except GeminiError as e:
            detail = redact(str(e))[:400]
            if e.i18n_key == "gemini.err_rate_limit":
                # "too many requests per minute": the key and the model work, Google only asks to slow down
                picked = model if model != service.model else None
                service.model = model
                return ConnectionTestResult(True, usable, None, now, picked_model=picked, detail=detail)
            if e.i18n_key in ("gemini.err_model", "gemini.err_bad_request", "gemini.err_no_free_quota"):
                continue  # this model is not usable (or not free) for this key: try the next one
            return ConnectionTestResult(False, usable, e.i18n_key, now, detail=detail)
        picked = model if model != service.model else None
        service.model = model
        return ConnectionTestResult(True, usable, None, now, picked_model=picked)
    return ConnectionTestResult(False, usable, "gemini.err_model", now, detail=detail)
