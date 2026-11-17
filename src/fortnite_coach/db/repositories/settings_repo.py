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
        try:
            return AppSettings.model_validate(row.value)
        except ValidationError:
            log.warning("Stored settings were invalid; using defaults")
            return AppSettings()


def save_settings(db: Database, settings: AppSettings) -> None:
    data = settings.model_dump(mode="json")
    with db.session() as s:
        row = s.get(Setting, KEY)
        if row is None:
            s.add(Setting(key=KEY, value=data))
        else:
            row.value = data
