"""Gemini API key storage in the OS credential store.

Windows: Windows Credential Manager (via the `keyring` package).
The key is NEVER written to the database, settings, logs or any file. If no secure
backend is available, saving fails with a clear error instead of falling back to
plain text.
"""

from __future__ import annotations

import logging
import re
import sys

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from fortnite_coach import APP_ID

log = logging.getLogger(__name__)
SERVICE = APP_ID
USERNAME = "gemini_api_key"

# Gemini keys are currently 39 chars starting with "AIza". We only reject input that
# clearly cannot be a key; whether it really works is decided by the connection test.
# Lenient on purpose: Google may change the key format (e.g. dots in newer keys). Whether a key
# really works is decided by the connection test, not by this check.
_ALLOWED = re.compile(r"^[A-Za-z0-9_\-.~+/=:]+$")
_LABEL = re.compile(r"^(?:gemini[_ ]?)?api[_ ]?key\s*[:=]\s*", re.IGNORECASE)


class KeyStoreError(Exception):
    def __init__(self, i18n_key: str):
        super().__init__(i18n_key)
        self.i18n_key = i18n_key


def validate_key_format(key: str) -> str:
    """Return the cleaned key or raise KeyStoreError with an i18n key."""
    k = (key or "").strip()
    k = _LABEL.sub("", k)                       # "API key: AIza..." -> "AIza..."
    k = k.strip().strip("\"'`“”‘’<>")  # surrounding quotes from copying
    k = re.sub(r"\s+", "", k)                   # spaces / line breaks added by copy-paste
    k = k.replace("\u200b", "").replace("\ufeff", "")  # invisible characters
    if not k:
        raise KeyStoreError("apikey.err_empty")
    if not _ALLOWED.match(k) or not (20 <= len(k) <= 300):
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
        if sys.platform == "win32":
            return "Windows" in type(kr).__module__ or getattr(kr, "priority", 0) > 0
        return getattr(kr, "priority", 0) > 0 and "fail" not in type(kr).__module__

    def save(self, key: str) -> None:
        clean = validate_key_format(key)
        if not self.backend_available():
            raise KeyStoreError("apikey.err_no_backend")
        try:
            keyring.set_password(self.service, USERNAME, clean)
        except Exception as e:  # KeyringError, or a raw Windows error from Credential Manager
            log.error("Could not save API key: %s", type(e).__name__)  # never log the key
            raise KeyStoreError("apikey.err_save") from e

    def load(self) -> str | None:
        try:
            return keyring.get_password(self.service, USERNAME)
        except Exception as e:  # never let Credential Manager problems stop the app from opening
            log.warning("Could not read the API key from secure storage: %s", type(e).__name__)
            return None

    def has_key(self) -> bool:
        return bool(self.load())

    def delete(self) -> None:
        try:
            keyring.delete_password(self.service, USERNAME)
        except PasswordDeleteError:
            pass
        except Exception as e:
            raise KeyStoreError("apikey.err_save") from e
