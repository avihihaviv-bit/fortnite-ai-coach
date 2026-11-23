"""In-app updater with fake GitHub responses (TEST DATA). No network."""

import hashlib
import io
import json

import pytest

from fortnite_coach import updater

BASE = "https://github.com/avihihaviv-bit/fortnite-ai-coach/releases/download/v9.9.9/"
PAYLOAD = b"MZ TEST DATA installer bytes" * 1000


def release(tag="v9.9.9", with_sha=True, exe=True):
    assets = []
    if exe:
        assets.append({"name": "FortniteAICoach-Setup-9.9.9.exe", "browser_download_url": BASE + "FortniteAICoach-Setup-9.9.9.exe",
                       "size": len(PAYLOAD)})
    if with_sha:
        assets.append({"name": "FortniteAICoach-Setup-9.9.9.exe.sha256",
                       "browser_download_url": BASE + "FortniteAICoach-Setup-9.9.9.exe.sha256", "size": 90})
    return json.dumps({"tag_name": tag, "assets": assets, "body": "TEST DATA notes", "html_url": "x"}).encode()


class Resp(io.BytesIO):
    headers = {"Content-Length": str(len(PAYLOAD))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_versions():
    assert updater.is_newer("v1.6.2", "1.6.1")
    assert not updater.is_newer("v1.6.1", "1.6.1")
    assert not updater.is_newer("v1.5.9", "1.6.0")
    assert updater.is_newer("v1.10.0", "1.9.9")


def test_check_finds_newer_release():
    info = updater.check(fetch=lambda url, t: release())
    assert info.version == "9.9.9" and info.installer_url.endswith(".exe") and info.checksum_url.endswith(".sha256")


def test_check_when_current_or_no_release():
    assert updater.check(fetch=lambda url, t: release(tag="v0.0.1")) is None

    def not_found(url, t):
        raise Exception("HTTP Error 404: Not Found")

    assert updater.check(fetch=not_found) is None


def test_release_without_checksum_is_refused():
    with pytest.raises(updater.UpdateError) as e:
        updater.check(fetch=lambda url, t: release(with_sha=False))
    assert e.value.i18n_key == "update.err_no_checksum"


def test_download_verifies_checksum(tmp_path):
    info = updater.check(fetch=lambda url, t: release())
    good = hashlib.sha256(PAYLOAD).hexdigest()
    seen = []
    out = updater.download(info, tmp_path, progress=lambda d, t: seen.append(d),
                           fetch=lambda url, t: f"{good}  FortniteAICoach-Setup-9.9.9.exe\n".encode(),
                           opener=lambda req, timeout: Resp(PAYLOAD))
    assert out.read_bytes() == PAYLOAD and seen[-1] == len(PAYLOAD)
    with pytest.raises(updater.UpdateError) as e:
        updater.download(info, tmp_path / "bad", fetch=lambda url, t: ("0" * 64).encode(),
                         opener=lambda req, timeout: Resp(PAYLOAD))
    assert e.value.i18n_key == "update.err_checksum"
    assert not list((tmp_path / "bad").glob("*.exe"))  # a bad file is never kept


def test_download_only_from_this_project(tmp_path):
    info = updater.check(fetch=lambda url, t: release())
    info.installer_url = "https://evil.example/Setup.exe"
    with pytest.raises(updater.UpdateError) as e:
        updater.download(info, tmp_path, fetch=lambda url, t: b"", opener=lambda req, timeout: Resp(PAYLOAD))
    assert e.value.i18n_key == "update.err_bad_source"


def test_update_card_flow(qtbot, tmp_path, monkeypatch):
    from fortnite_coach.app import create_app
    from fortnite_coach.config.paths import AppPaths
    from fortnite_coach.db.engine import Database
    from fortnite_coach.i18n.translator import get_translator
    from fortnite_coach.ui.main_window import MainWindow
    from fortnite_coach.workers.task import wait_all

    create_app([])
    paths = AppPaths(tmp_path / "h").ensure()
    db = Database(paths.database).init()
    w = MainWindow(db, paths, recording_source="test")
    qtbot.addWidget(w)
    w.set_language("en")
    card = w.settings_page.update_card
    monkeypatch.setattr(updater, "check", lambda: updater.UpdateInfo("9.9.9", BASE + "a.exe", BASE + "a.exe.sha256",
                                                                     1000, "TEST DATA notes", "x"))
    card.check(manual=True)
    qtbot.waitUntil(lambda: card.state == "available", timeout=5000)
    assert "9.9.9 is available" in card.status.text() and card.install_btn.isVisibleTo(card)
    monkeypatch.setattr(updater, "can_self_update", lambda: False)
    card.install()
    assert card.state == "error" and "installed app" in card.status.text()
    # with a recording running, installing is refused
    monkeypatch.setattr(updater, "can_self_update", lambda: True)
    w.recording.start()
    card.install()
    assert "Stop recording" in card.status.text()
    w.recording.stop()
    # download + verified installer -> installer started and app quits
    launched, quit_called = [], []
    monkeypatch.setattr(updater, "download", lambda info, folder, progress, cancel: tmp_path / "Setup.exe")
    monkeypatch.setattr(updater, "launch_installer", launched.append)
    monkeypatch.setattr(w, "quit_app", lambda: quit_called.append(1))
    card.confirm = lambda *a: True
    card.install()
    qtbot.waitUntil(lambda: bool(quit_called), timeout=5000)
    assert launched == [tmp_path / "Setup.exe"]
    wait_all()
    w._quitting = True
    db.close()
    get_translator().set_language("he")
