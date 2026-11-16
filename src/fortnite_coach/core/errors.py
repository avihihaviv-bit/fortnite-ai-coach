"""Application error hierarchy. Every error carries a user-facing i18n key."""

from __future__ import annotations


class CoachError(Exception):
    i18n_key = "error.generic"

    def __init__(self, message: str = "", *, i18n_key: str | None = None, **params: object):
        super().__init__(message or self.__class__.__name__)
        if i18n_key:
            self.i18n_key = i18n_key
        self.params = params


class VideoError(CoachError):
    i18n_key = "error.video"


class FFmpegNotFoundError(VideoError):
    i18n_key = "error.ffmpeg_missing"


class GeminiError(CoachError):
    i18n_key = "error.gemini"


class GeminiNotConfiguredError(GeminiError):
    i18n_key = "gemini.not_configured"


class UsageLimitExceededError(GeminiError):
    i18n_key = "error.usage_limit"


class OperationCancelledError(CoachError):
    i18n_key = "error.cancelled"
