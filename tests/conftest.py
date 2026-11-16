"""Shared test fixtures. Tests never need a Gemini API key."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Every test gets its own empty data directory."""
    home = tmp_path / "coach_home"
    monkeypatch.setenv("FORTNITE_COACH_HOME", str(home))
    return home
