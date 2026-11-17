"""Shared services handed to pages (instead of globals)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fortnite_coach.ai.key_store import KeyStore
from fortnite_coach.ai.status import GeminiStatus
from fortnite_coach.config.paths import AppPaths
from fortnite_coach.config.settings import AppSettings
from fortnite_coach.db.engine import Database
from fortnite_coach.recording.controller import RecordingController


@dataclass
class AppContext:
    db: Database
    paths: AppPaths
    settings: Callable[[], AppSettings]
    save_settings: Callable[[AppSettings], None]
    recording: RecordingController
    key_store: KeyStore
    gemini_status: Callable[[], GeminiStatus]
    gemini_service: Callable[[], object]   # -> GeminiService for the selected model
    open_report: Callable[..., None]     # navigate to a report in History
    data_changed: Callable[[], None]       # refresh everything after a DB change
