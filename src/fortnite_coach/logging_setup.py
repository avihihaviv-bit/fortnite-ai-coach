"""File logging for the desktop app (a windowed EXE has no console).

Secrets are redacted before anything is written: Gemini-style keys are masked by
pattern, and any value registered with `register_secret` is masked too.
"""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_\-]{20,}")
_secrets: set[str] = set()


def register_secret(value: str | None) -> None:
    if value and len(value) >= 8:
        _secrets.add(value)


def redact(text: str) -> str:
    text = _KEY_PATTERN.sub("[REDACTED]", text)
    for s in _secrets:
        text = text.replace(s, "[REDACTED]")
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def setup_logging(logs_dir: Path, level: int = logging.INFO) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "app.log"
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, "_coach", False):
            root.removeHandler(h)
            h.close()
    handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler._coach = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level)
    return log_file
