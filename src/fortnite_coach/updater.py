"""Check for a newer version on GitHub Releases, download it, verify it, and run the installer.

- Only this project's public releases are used (api.github.com / github.com), no login.
- The installer is downloaded only if the release also has its SHA-256 file, and it is run only if the
  downloaded file matches that checksum.
- Nothing is installed without the player clicking "Install update".
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from fortnite_coach import __version__

log = logging.getLogger(__name__)

REPO = "avihihaviv-bit/fortnite-ai-coach"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
ALLOWED_PREFIXES = (f"https://github.com/{REPO}/releases/download/", "https://objects.githubusercontent.com/",
                    "https://release-assets.githubusercontent.com/")
USER_AGENT = "FortniteAICoach-Updater"


class UpdateError(Exception):
    def __init__(self, i18n_key: str, detail: str = ""):
        super().__init__(detail or i18n_key)
        self.i18n_key = i18n_key


@dataclass
class UpdateInfo:
    version: str
    installer_url: str
    checksum_url: str
    size: int
    notes: str
    page_url: str


def parse_version(text: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in nums[:3]) or (0,)


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


def _get(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - fixed https URLs only
        return r.read()


def check(timeout: float = 15, fetch=_get) -> UpdateInfo | None:
    """The newer release, or None when this is the newest version."""
    try:
        data = json.loads(fetch(LATEST_URL, timeout))
    except Exception as e:
        if "404" in str(e):
            return None  # no release published yet
        raise UpdateError("update.err_network", str(e)[:200]) from e
    tag = data.get("tag_name", "")
    if not is_newer(tag):
        return None
    assets = {a.get("name", ""): a for a in data.get("assets", [])}
    exe = next((a for n, a in assets.items() if n.lower().endswith(".exe") and "setup" in n.lower()), None)
    if exe is None:
        raise UpdateError("update.err_no_installer")
    sha = assets.get(exe["name"] + ".sha256")
    if sha is None:
        raise UpdateError("update.err_no_checksum")
    return UpdateInfo(version=tag.lstrip("v"), installer_url=exe["browser_download_url"],
                      checksum_url=sha["browser_download_url"], size=int(exe.get("size") or 0),
                      notes=(data.get("body") or "")[:1500], page_url=data.get("html_url", ""))


def _check_url(url: str) -> None:
    if not url.startswith(ALLOWED_PREFIXES):
        raise UpdateError("update.err_bad_source", url[:120])


def download(info: UpdateInfo, folder: Path, progress=lambda done, total: None,
             cancel: threading.Event | None = None, fetch=_get, opener=None) -> Path:
    """Download the installer and verify its SHA-256. Returns the verified file."""
    _check_url(info.installer_url)
    _check_url(info.checksum_url)
    try:
        expected = fetch(info.checksum_url, 30).decode("utf-8", "replace").split()[0].strip().lower()
    except Exception as e:
        raise UpdateError("update.err_network", str(e)[:200]) from e
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise UpdateError("update.err_no_checksum")
    folder.mkdir(parents=True, exist_ok=True)
    cleanup(folder)  # never keep old 200 MB installers around
    out = folder / f"FortniteAICoach-Setup-{info.version}.exe"
    part = out.with_suffix(".part")
    h = hashlib.sha256()
    try:
        req = urllib.request.Request(info.installer_url, headers={"User-Agent": USER_AGENT})
        with (opener or urllib.request.urlopen)(req, timeout=60) as r, open(part, "wb") as f:  # noqa: S310
            total = int(r.headers.get("Content-Length") or info.size or 0)
            done = 0
            while True:
                if cancel is not None and cancel.is_set():
                    raise UpdateError("update.cancelled")
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                progress(done, total)
    except UpdateError:
        part.unlink(missing_ok=True)
        raise
    except Exception as e:
        part.unlink(missing_ok=True)
        raise UpdateError("update.err_network", str(e)[:200]) from e
    if h.hexdigest() != expected:
        part.unlink(missing_ok=True)
        raise UpdateError("update.err_checksum")
    part.replace(out)
    return out


def cleanup(folder: Path) -> int:
    """Delete downloaded installers (after an update finished they are not needed). Returns bytes freed."""
    freed = 0
    if folder.is_dir():
        for p in folder.iterdir():
            try:
                size = p.stat().st_size
                p.unlink()
                freed += size
            except OSError:
                pass  # still in use (the installer is finishing): next start removes it
    return freed


def can_self_update() -> bool:
    """Only the installed Windows app updates itself (not when running from source)."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def launch_installer(path: Path) -> None:  # pragma: no cover - Windows only
    """Run the verified installer with a progress window; it closes this app, upgrades, and starts it again."""
    import ctypes

    params = "/SILENT /SUPPRESSMSGBOXES /NORESTART /RELAUNCH=1"
    rc = ctypes.windll.shell32.ShellExecuteW(None, "open", str(path), params, None, 1)
    if rc <= 32:
        raise UpdateError("update.err_launch", f"ShellExecute {rc}")
