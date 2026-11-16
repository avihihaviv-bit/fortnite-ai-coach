"""Minimal JSON-based translator with runtime language switching.

Usage:  tr("nav.dashboard")  or  tr("analysis.duration", seconds=42)
Missing keys fall back to English, then to the key itself (so a missing
translation is visible during development instead of crashing).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache

from fortnite_coach.config.paths import resource_path

RTL_LANGUAGES = frozenset({"he"})
FALLBACK = "en"


@lru_cache(maxsize=None)
def load_catalog(lang: str) -> dict[str, str]:
    path = resource_path(f"i18n/{lang}.json")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


class Translator:
    def __init__(self, language: str = "he"):
        self._language = language
        self._listeners: list[Callable[[str], None]] = []

    @property
    def language(self) -> str:
        return self._language

    @property
    def is_rtl(self) -> bool:
        return self._language in RTL_LANGUAGES

    def set_language(self, language: str) -> None:
        load_catalog(language)  # validate it exists before switching
        if language == self._language:
            return
        self._language = language
        for cb in list(self._listeners):
            cb(language)

    def on_change(self, callback: Callable[[str], None]) -> None:
        self._listeners.append(callback)

    def tr(self, key: str, **params: object) -> str:
        text = load_catalog(self._language).get(key)
        if text is None:
            text = load_catalog(FALLBACK).get(key, key)
        if params:
            try:
                text = text.format(**params)
            except (KeyError, IndexError, ValueError):
                pass
        return text


_translator = Translator()


def get_translator() -> Translator:
    return _translator


def tr(key: str, **params: object) -> str:
    return _translator.tr(key, **params)
