"""Gemini API key storage in the OS credential store.

Windows: Windows Credential Manager (via the `keyring` package).
The key is NEVER written to the database, settings, logs or any file. If no secure
backend is available, saving fails with a clear error instead of falling back to
plain text.
"""

from __future__ import annotations

import logging
import re

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from fortnite_coach import APP_ID

log = logging.getLogger(__name__)
SERVICE = APP_ID
USERNAME = "gemini_api_key"

# Gemini keys are currently 39 chars starting with "AIza". We only reject input that
# clearly cannot be a key; whether it really works is decided by the connection test.
_ALLOWED = re.compile(r"^[A-Za-z0-9_\-]+$")


class KeyStoreError(Exception):
    def __init__(self, i18n_key: str):
        super().__init__(i18n_key)
        self.i18n_key = i18n_key


def validate_key_format(key: str) -> str:
    """Return the cleaned key or raise KeyStoreError with an i18n key."""
    k = (key or "").strip()
    if not k:
        raise KeyStoreError("apikey.err_empty")
    if not _ALLOWED.match(k) or not (20 <= len(k) <= 200):
        raise KeyStoreError("apikey.err_format")
    return k


def looks_like_gemini_key(key: str) -> bool:
    return key.startswith("AIza") and len(key) == 39


def mask(key: str) -> str:
    return "•" * 8 + key[-4:] if len(key) > 8 else "•" * len(key)


class KeyStore:
    def __init__(self, service: str = SERVICE):
        self.service = service

    def backend_available(self) -> bool:
        try:
            kr = keyring.get_keyring()
        except Exception:  # pragma: no cover
            return False
        return getattr(kr, "priority", 0) > 0 and "fail" not in type(kr).__module__

    def save(self, key: str) -> None:
        clean = validate_key_format(key)
        if not self.backend_available():
            raise KeyStoreError("apikey.err_no_backend")
        try:
            keyring.set_password(self.service, USERNAME, clean)
        except KeyringError as e:
            log.error("Could not save API key: %s", type(e).__name__)  # never log the key
            raise KeyStoreError("apikey.err_save") from e

    def load(self) -> str | None:
        try:
            return keyring.get_password(self.service, USERNAME)
        except KeyringError:
            return None

    def has_key(self) -> bool:
        return bool(self.load())

    def delete(self) -> None:
        try:
            keyring.delete_password(self.service, USERNAME)
        except PasswordDeleteError:
            pass
        except KeyringError as e:
            raise KeyStoreError("apikey.err_save") from e
