"""Packaging checks that run on any OS (the real EXE is built and smoke-tested on Windows CI)."""

import ast
import json
import logging
import re
import sys
import tomllib
from pathlib import Path

import pytest

from fortnite_coach import __version__

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "fortnite_coach"


def _spec_patterns() -> list[str]:
    tree = ast.parse((ROOT / "packaging" / "fortnite_coach.spec").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "DATA_PATTERNS":
            return ast.literal_eval(node.value)
    raise AssertionError("DATA_PATTERNS not found")


def test_spec_bundles_every_package_data_file():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    declared = pyproject["tool"]["setuptools"]["package-data"]["fortnite_coach"]
    spec = _spec_patterns()
    assert set(declared) <= set(spec)
    for pattern in spec:
        assert list(PKG.glob(pattern)), f"pattern matches nothing: {pattern}"


def test_every_runtime_resource_is_covered_by_the_spec():
    """Any non-Python file inside the package must be bundled, or the EXE breaks at runtime."""
    covered = {f for p in _spec_patterns() for f in PKG.glob(p)}
    runtime = {f for f in PKG.rglob("*") if f.is_file() and f.suffix in (".json", ".qss", ".png", ".ico", ".svg")}
    assert runtime <= covered, sorted(str(f.relative_to(PKG)) for f in runtime - covered)


def test_versions_in_sync():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == __version__
    vi = (ROOT / "packaging" / "version_info.txt").read_text()
    assert f"'FileVersion', '{__version__}'" in vi and f"'ProductVersion', '{__version__}'" in vi
    nums = tuple(int(x) for x in __version__.split("."))
    assert f"filevers=({nums[0]}, {nums[1]}, {nums[2]}, 0)" in vi


def test_installer_script_keeps_user_data_and_is_per_user():
    iss = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in iss
    assert "Hebrew.isl" in iss
    assert "{userappdata}" not in iss.lower() and "[UninstallDelete]" not in iss  # never deletes user data
    assert "dist\\FortniteAICoach\\*" in iss


def test_icon_is_valid_multi_size_ico():
    data = (PKG / "assets" / "app.ico").read_bytes()
    reserved, kind, count = __import__("struct").unpack("<HHH", data[:6])
    assert (reserved, kind) == (0, 1) and count >= 5


def test_resource_path_in_frozen_layout(monkeypatch, tmp_path):
    from fortnite_coach.config import paths

    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert paths.resource_path("i18n/en.json") == tmp_path / "fortnite_coach" / "i18n" / "en.json"


def test_bundled_ffmpeg_preferred_in_frozen_layout(monkeypatch, tmp_path):
    from fortnite_coach.video import ffmpeg_tools

    exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    (tmp_path / "ffmpeg").mkdir()
    (tmp_path / "ffmpeg" / exe).write_bytes(b"")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.delenv(ffmpeg_tools.ENV_FFMPEG, raising=False)
    assert ffmpeg_tools.find_ffmpeg() == str(tmp_path / "ffmpeg" / exe)


def test_self_test_passes_from_source(tmp_path):
    from fortnite_coach.selftest import main

    out = tmp_path / "st.json"
    assert main(str(out)) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["ok"] and report["version"] == __version__
    assert {c["check"] for c in report["checks"]} == {"resources", "database", "ffmpeg", "keyring", "qt"}


def test_self_test_cli_entry(tmp_path):
    from fortnite_coach.app import run

    out = tmp_path / "cli.json"
    assert run(["prog", "--self-test", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["ok"]


def test_single_instance(qtbot):
    """The second launch is a separate process, exactly like a real double-click."""
    import subprocess

    from fortnite_coach.app import create_app
    from fortnite_coach.single_instance import SingleInstance, server_name

    create_app([])
    name = server_name("-test")
    first = SingleInstance(name)
    assert not first.notify_running_instance(200)  # nobody running yet
    assert first.listen()
    code = ("import sys; from PySide6.QtCore import QCoreApplication; app = QCoreApplication([]); "
            "from fortnite_coach.single_instance import SingleInstance; "
            f"sys.exit(0 if SingleInstance({name!r}).notify_running_instance(3000) else 3)")
    src = str(ROOT / "src")
    with qtbot.waitSignal(first.activated, timeout=10000):
        proc = subprocess.Popen([sys.executable, "-c", code], env={**__import__("os").environ, "PYTHONPATH": src})
    qtbot.waitUntil(lambda: proc.poll() is not None, timeout=10000)
    assert proc.returncode == 0
    first.close()


def test_log_redacts_api_keys(tmp_path):
    from fortnite_coach.logging_setup import register_secret, setup_logging

    secret = "AIza" + "Z" * 35  # TEST DATA
    other = "custom-secret-value-123"
    register_secret(other)
    log_file = setup_logging(tmp_path / "logs")
    logging.getLogger("t").error("key=%s other=%s", secret, other)
    for h in logging.getLogger().handlers:
        h.flush()
    text = log_file.read_text(encoding="utf-8")
    assert secret not in text and other not in text and text.count("[REDACTED]") == 2


def test_crash_hook_logs(tmp_path, monkeypatch):
    from fortnite_coach import crash
    from fortnite_coach.logging_setup import setup_logging

    log_file = setup_logging(tmp_path / "logs")
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    crash.install_excepthook(str(log_file), show_dialog=False)
    try:
        raise RuntimeError("boom-test")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    for h in logging.getLogger().handlers:
        h.flush()
    assert "boom-test" in log_file.read_text(encoding="utf-8")


def test_workflow_smoke_tests_built_and_installed_exe():
    wf = (ROOT / ".github" / "workflows" / "build-windows.yml").read_text()
    assert "windows-latest" in wf and "--self-test" in wf
    assert wf.count("--self-test") >= 2  # built EXE and installed EXE
    assert "fetch_ffmpeg.ps1" in wf and "pytest" in wf


def test_ffmpeg_fetch_script_verifies_hash():
    ps = (ROOT / "packaging" / "fetch_ffmpeg.ps1").read_text()
    assert "Get-FileHash" in ps and "SHA-256 mismatch" in ps
    assert "Candidates" in ps and "latest" not in ps.lower()  # fixed versions only, never "latest"
