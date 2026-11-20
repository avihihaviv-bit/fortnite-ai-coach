"""GeminiService: the only place that talks to the Gemini API.

- Client is created lazily from the key in Windows Credential Manager (never from files).
- Retries only transient failures (429 rate limit, 5xx, timeouts, network), with backoff
  that honors the server's suggested retry delay. Auth/quota/model errors fail fast.
- A client factory can be injected so all tests run without a key or network.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fortnite_coach.core.errors import GeminiError, GeminiNotConfiguredError, OperationCancelledError

log = logging.getLogger(__name__)
MAX_RETRY_DELAY_S = 60.0
UPLOAD_POLL_S = 3.0
UPLOAD_TIMEOUT_S = 600.0


@dataclass
class ClassifiedError:
    i18n_key: str
    retryable: bool
    delay_s: float | None = None


def _status_code(exc: Exception) -> int | None:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    try:
        return int(code) if code is not None else None
    except (TypeError, ValueError):
        return None


def classify(exc: Exception) -> ClassifiedError:
    """Map any exception from the SDK/network to a user message and retry decision."""
    text = f"{type(exc).__name__} {exc}"
    low = text.lower()
    code = _status_code(exc)
    m = re.search(r"retry(?:delay)?[\"': in]+(\d+(?:\.\d+)?)s", low)
    delay = float(m.group(1)) if m else None
    if code == 429 or "resource_exhausted" in low:
        if re.search(r"limit[\"': ]+0\b", low):
            # "limit: 0": this model has NO free quota for this key (not "used up today")
            return ClassifiedError("gemini.err_no_free_quota", False)
        if "perday" in low.replace(" ", "") or "per day" in low or (delay and delay > MAX_RETRY_DELAY_S):
            return ClassifiedError("gemini.err_quota_daily", False)
        return ClassifiedError("gemini.err_rate_limit", True, delay)
    if "location is not supported" in low or "user location" in low:
        return ClassifiedError("gemini.err_region", False)
    if code in (401, 403) or "api key not valid" in low or "api_key_invalid" in low or "permission_denied" in low \
            or "api key expired" in low:
        return ClassifiedError("gemini.err_key", False)
    if code == 404 or (code is None and ("not_found" in low or "not found" in low)):
        if "file" in low and "model" not in low:
            return ClassifiedError("gemini.err_file", False)  # uploaded video expired / missing
        return ClassifiedError("gemini.err_model", False)  # e.g. "no longer available to new users"
    if "no longer available" in low:
        return ClassifiedError("gemini.err_model", False)
    if code == 400 and ("safety" in low or "blocked" in low):
        return ClassifiedError("gemini.err_blocked", False)
    if code == 400:
        return ClassifiedError("gemini.err_bad_request", False)
    if code is not None and code >= 500:
        return ClassifiedError("gemini.err_server", True, delay)
    if any(w in low for w in ("timeout", "timed out", "connecterror", "connection", "network", "remotedisconnected")):
        return ClassifiedError("gemini.err_network", True, delay)
    return ClassifiedError("gemini.err_unknown", False)


def _default_client_factory(api_key: str, timeout_s: int):
    from google import genai
    from google.genai import types

    # Uploading a video can take minutes on a slow connection: never shorter than 10 minutes.
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=max(timeout_s, 600) * 1000))


@dataclass
class UploadedFile:
    name: str
    uri: str
    mime_type: str
    inline_path: Path | None = None  # small videos are sent inside the request instead of via the Files API


@dataclass
class GenerateResult:
    text: str
    prompt_tokens: int | None
    output_tokens: int | None


class GeminiService:
    def __init__(
        self,
        api_key_provider: Callable[[], str | None],
        model: str,
        *,
        timeout_s: int = 180,
        max_retries: int = 3,
        client_factory: Callable[[str, int], Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._key = api_key_provider
        self.model = model
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self._factory = client_factory or _default_client_factory
        self._sleep = sleep
        self._client = None

    @property
    def client(self):
        if self._client is None:
            key = self._key()
            if not key:
                raise GeminiNotConfiguredError("no key")
            self._client = self._factory(key, self.timeout_s)
        return self._client

    # ---------------------------------------------------------------- calls
    def _with_retries(self, fn: Callable[[], Any], cancel: threading.Event | None = None) -> Any:
        attempt = 0
        while True:
            if cancel is not None and cancel.is_set():
                raise OperationCancelledError()
            try:
                return fn()
            except (GeminiError, OperationCancelledError):
                raise
            except Exception as exc:  # SDK / network errors
                c = classify(exc)
                from fortnite_coach.logging_setup import redact

                log.warning("Gemini call failed (%s, retryable=%s): %s: %s", c.i18n_key, c.retryable,
                            type(exc).__name__, redact(str(exc))[:500])
                if not c.retryable or attempt >= self.max_retries:
                    raise GeminiError(str(exc)[:300], i18n_key=c.i18n_key) from exc
                delay = min(MAX_RETRY_DELAY_S, c.delay_s if c.delay_s else 2.0 * (2 ** attempt))
                attempt += 1
                self._sleep(delay)

    PING = "Reply with the single word OK."

    def ping(self, model: str | None = None) -> None:
        """A tiny real generation request: proves the model is usable for this key, not just listed."""
        from google.genai import types

        target = model or self.model
        self._with_retries(lambda: self.client.models.generate_content(
            model=target, contents=self.PING, config=types.GenerateContentConfig(max_output_tokens=64, temperature=0)))

    def list_models(self) -> list[str]:
        def call():
            names = []
            for m in self.client.models.list():
                name = getattr(m, "name", "") or ""
                actions = getattr(m, "supported_actions", None)
                if actions is not None and "generateContent" not in actions:
                    continue
                names.append(name.removeprefix("models/"))
            return names

        return self._with_retries(call)

    def upload_video(self, path: Path, mime_type: str, cancel: threading.Event | None = None) -> UploadedFile:
        f = self._with_retries(lambda: self.client.files.upload(file=str(path), config={"mime_type": mime_type}), cancel)
        deadline = time.monotonic() + UPLOAD_TIMEOUT_S
        while self._state(f) == "PROCESSING":
            if cancel is not None and cancel.is_set():
                raise OperationCancelledError()
            if time.monotonic() > deadline:
                raise GeminiError("processing timeout", i18n_key="gemini.err_processing")
            self._sleep(UPLOAD_POLL_S)
            f = self._with_retries(lambda: self.client.files.get(name=f.name), cancel)
        if self._state(f) != "ACTIVE":
            raise GeminiError(f"file state {self._state(f)}", i18n_key="gemini.err_processing")
        return UploadedFile(name=f.name, uri=f.uri, mime_type=getattr(f, "mime_type", None) or mime_type)

    def delete_file(self, name: str) -> bool:
        try:
            self.client.files.delete(name=name)
            return True
        except Exception as exc:
            log.warning("Could not delete uploaded file (%s)", classify(exc).i18n_key)
            return False

    def file_is_active(self, name: str) -> bool:
        try:
            return self._state(self.client.files.get(name=name)) == "ACTIVE"
        except Exception:
            return False

    @staticmethod
    def _state(f) -> str:
        state = getattr(f, "state", None)
        return str(getattr(state, "name", state) or "").upper().split(".")[-1]

    def generate_segment(
        self, file: UploadedFile, start_s: float, end_s: float, fps: float, low_resolution: bool,
        system_instruction: str, prompt: str, schema: type, cancel: threading.Event | None = None,
        whole_video: bool = False,
    ) -> GenerateResult:
        """whole_video: the segment is the entire file, so no cut points are sent (one fewer feature to rely on)."""
        from google.genai import types

        inline_bytes = file.inline_path.read_bytes() if file.inline_path else None

        def build(minimal: bool):
            offsets = {} if whole_video else {"start_offset": f"{start_s:.1f}s", "end_offset": f"{end_s:.1f}s"}
            rate = None if minimal else fps
            meta = types.VideoMetadata(**offsets, fps=rate) if (offsets or rate) else None
            if inline_bytes is not None:
                video = types.Part(inline_data=types.Blob(data=inline_bytes, mime_type=file.mime_type), video_metadata=meta)
            else:
                video = types.Part(file_data=types.FileData(file_uri=file.uri, mime_type=file.mime_type),
                                   video_metadata=meta)
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.2,
                media_resolution=None if minimal else (types.MediaResolution.MEDIA_RESOLUTION_LOW if low_resolution
                                                       else types.MediaResolution.MEDIA_RESOLUTION_MEDIUM),
            )
            return [types.Content(role="user", parts=[video, types.Part(text=prompt)])], config

        def call(minimal: bool):
            contents, config = build(minimal)
            resp = self.client.models.generate_content(model=self.model, contents=contents, config=config)
            text = getattr(resp, "text", None)
            if not text:
                reason = ""
                cands = getattr(resp, "candidates", None) or []
                if cands:
                    reason = str(getattr(cands[0], "finish_reason", "") or "")
                raise GeminiError(f"empty response {reason}".strip(), i18n_key="gemini.err_blocked")
            usage = getattr(resp, "usage_metadata", None)
            out_tokens = (getattr(usage, "candidates_token_count", None) or 0) + (getattr(usage, "thoughts_token_count", None) or 0)
            return GenerateResult(text, getattr(usage, "prompt_token_count", None), out_tokens or None)

        try:
            return self._with_retries(lambda: call(False), cancel)
        except GeminiError as e:
            if e.i18n_key != "gemini.err_bad_request":
                raise
            # Some models reject optional video settings (custom fps / media resolution): retry once without them.
            log.warning("Retrying segment without optional video settings after: %s", str(e)[:200])
            return self._with_retries(lambda: call(True), cancel)
