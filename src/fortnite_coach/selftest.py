"""`--self-test`: a non-GUI health check of an installed or source build.

Used by the Windows CI build to verify the packaged EXE, and by users for diagnostics.
It never touches the real user data folder or the real stored API key.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


def _check(name: str, fn, results: list[dict], required: bool = True) -> None:
    try:
        detail = fn()
        results.append({"check": name, "ok": True, "required": required, "detail": detail})
    except Exception as e:  # report, never crash the self-test
        results.append({"check": name, "ok": False, "required": required, "detail": f"{type(e).__name__}: {e}"})


def run_self_test() -> dict:
    from fortnite_coach import __version__

    results: list[dict] = []
    frozen = bool(getattr(sys, "frozen", False))

    def resources():
        from fortnite_coach.config.paths import resource_path
        from fortnite_coach.i18n.translator import load_catalog
        from fortnite_coach.db.repositories.knowledge_repo import load_builtin_pack
        from fortnite_coach.ui.theme import stylesheet

        en, he = load_catalog("en"), load_catalog("he")
        assert en.keys() == he.keys(), "catalog keys differ"
        assert "@" not in stylesheet().replace("@media", ""), "unresolved stylesheet tokens"
        n = len(load_builtin_pack()["entries"])
        return f"{len(en)} strings, {n} knowledge entries, base {resource_path('')}"

    def database():
        from fortnite_coach.db.engine import Database
        from fortnite_coach.db.migrations import LATEST_VERSION
        from fortnite_coach.db.repositories.knowledge_repo import seed_builtin

        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "selftest.db").init()
            seed_builtin(db)
            db.close()
        return f"schema v{LATEST_VERSION}"

    def ffmpeg():
        from fortnite_coach.recording.capabilities import parse_encoders, parse_names, test_encoder
        from fortnite_coach.video.ffmpeg_tools import find_ffmpeg, find_ffprobe, run

        exe, probe = find_ffmpeg(), find_ffprobe()
        encoders = parse_encoders(run([exe, "-hide_banner", "-encoders"], timeout=30).stdout)
        filters = parse_names(run([exe, "-hide_banner", "-filters"], timeout=30).stdout, ("ddagrab",))
        assert test_encoder(exe, "libx264"), "libx264 test encode failed"
        info = {"ffmpeg": exe, "ffprobe": probe, "ddagrab": "ddagrab" in filters,
                "nvenc_built": "h264_nvenc" in encoders, "amf_built": "h264_amf" in encoders,
                "qsv_built": "h264_qsv" in encoders}
        if frozen and sys.platform == "win32":
            assert info["ddagrab"], "bundled ffmpeg lacks ddagrab"
            assert "ffmpeg" in Path(exe).parent.name.lower() or "_internal" in exe, "not the bundled ffmpeg"
        return info

    def keyring_backend():
        import keyring

        name = type(keyring.get_keyring()).__module__
        if sys.platform == "win32":
            assert "Windows" in name, f"unexpected backend {name}"
        return name

    def qt():
        from PySide6.QtCore import qVersion
        from PySide6.QtGui import QGuiApplication  # noqa: F401  (import check only)

        return qVersion()

    _check("resources", resources, results)
    _check("database", database, results)
    _check("ffmpeg", ffmpeg, results)
    _check("keyring", keyring_backend, results, required=sys.platform == "win32")
    _check("qt", qt, results)
    ok = all(r["ok"] for r in results if r["required"])
    return {"version": __version__, "frozen": frozen, "platform": sys.platform, "ok": ok, "checks": results}


def main(out_path: str | None) -> int:
    report = run_self_test()
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if out_path:
        Path(out_path).write_text(text, encoding="utf-8")
    if sys.stdout is not None:  # a windowed EXE has no stdout
        try:
            print(text)
        except OSError:
            pass
    return 0 if report["ok"] else 1
