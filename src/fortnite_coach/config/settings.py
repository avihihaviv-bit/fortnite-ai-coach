"""Application settings (non-secret).

The Gemini API key is NOT part of these settings: it is stored only in the
OS credential store (Windows Credential Manager) - see ai/key_store.py.
Settings are persisted in the SQLite `settings` table (see db/).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    HEBREW = "he"
    ENGLISH = "en"


class UsageLimits(BaseModel):
    """Hard limits checked BEFORE any Gemini request is sent."""

    max_requests_per_day: int = Field(default=20, ge=0, le=1000)
    max_video_seconds: int = Field(default=300, ge=10, le=3600)
    max_frames_per_analysis: int = Field(default=24, ge=1, le=200)
    max_upload_mb: int = Field(default=100, ge=1, le=2000)


class GeminiSettings(BaseModel):
    # Free-tier-first: a Flash-class model. The connection test checks that the
    # model actually exists for the user's key; we never switch models silently.
    model: str = "gemini-2.5-flash"
    request_timeout_s: int = Field(default=180, ge=10, le=900)
    max_retries: int = Field(default=3, ge=0, le=5)
    # The user must explicitly acknowledge that their account may be billed
    # before the app sends requests to a model they marked as paid.
    paid_usage_acknowledged: bool = False


class AppSettings(BaseModel):
    language: Language = Language.HEBREW
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    confirm_before_each_request: bool = True
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    limits: UsageLimits = Field(default_factory=UsageLimits)
