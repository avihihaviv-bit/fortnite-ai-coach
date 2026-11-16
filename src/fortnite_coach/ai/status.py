"""Gemini connection status shown across the UI."""

from __future__ import annotations

from enum import Enum


class GeminiStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"          # no key saved
    CONFIGURED_UNTESTED = "configured_untested"  # key saved, never tested
    CONNECTED = "connected"                    # last connection test succeeded
    ERROR = "error"                            # last connection test failed

    @property
    def i18n_key(self) -> str:
        return f"gemini.{self.value}"

    @property
    def pill_state(self) -> str:
        return {
            GeminiStatus.NOT_CONFIGURED: "off",
            GeminiStatus.CONFIGURED_UNTESTED: "warn",
            GeminiStatus.CONNECTED: "ok",
            GeminiStatus.ERROR: "error",
        }[self]

    @property
    def can_analyze(self) -> bool:
        return self is GeminiStatus.CONNECTED
