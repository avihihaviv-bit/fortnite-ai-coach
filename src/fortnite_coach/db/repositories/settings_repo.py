"""Persist AppSettings as one JSON row. Invalid stored data falls back to defaults."""

from __future__ import annotations

import logging

from pydantic import ValidationError

from fortnite_coach.config.settings import AppSettings
from fortnite_coach.db.engine import Database
from fortnite_coach.db.models import Setting

log = logging.getLogger(__name__)
KEY = "app_settings"


def load_settings(db: Database) -> AppSettings:
    with db.session() as s:
        row = s.get(Setting, KEY)
        if row is None:
            return AppSettings()
        return _upgrade(_validate(row.value))


def _validate(data: dict) -> AppSettings:
    try:
        return AppSettings.model_validate(data)
    except ValidationError:
        # keep every section that is still valid instead of losing all settings
        log.warning("Some stored settings were invalid; keeping the valid parts")
        kept = {}
        for key, value in (data or {}).items():
            try:
                AppSettings.model_validate({key: value})
                kept[key] = value
            except ValidationError:
                continue
        return AppSettings.model_validate(kept)


def _upgrade(s: AppSettings) -> AppSettings:
    if s.settings_version < 2:
        # 1.6: Live on/off moved from Ctrl+Shift+F11 to F3 (unless the player had chosen another key)
        if s.live.hotkey == "Ctrl+Shift+F11":
            s.live.hotkey = "F3"
        s.settings_version = 2
    if s.settings_version < 3:
        # 1.7: analyze up to 10 minutes by default (was 5), unless the player had changed it
        if s.limits.max_video_seconds == 300:
            s.limits.max_video_seconds = 600
        s.settings_version = 3
    return s


def save_settings(db: Database, settings: AppSettings) -> None:
    data = settings.model_dump(mode="json")
    with db.session() as s:
        row = s.get(Setting, KEY)
        if row is None:
            s.add(Setting(key=KEY, value=data))
        else:
            row.value = data
