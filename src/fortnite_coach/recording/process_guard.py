"""One-shot check whether Fortnite is running (used only when the user clicks Analyze).

There is no monitoring loop: `tasklist` is run once, on demand. The game process
is never opened, read or touched.
"""

from __future__ import annotations

import subprocess
import sys

from fortnite_coach.video.ffmpeg_tools import run

FORTNITE_PROCESSES = ("FortniteClient-Win64-Shipping.exe", "FortniteLauncher.exe")


def parse_tasklist(output: str) -> bool:
    low = output.lower()
    return any(name.lower() in low for name in FORTNITE_PROCESSES)


def is_fortnite_running() -> bool:
    if sys.platform != "win32":
        return False
    try:
        res = run(["tasklist", "/FO", "CSV", "/NH"], timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return parse_tasklist(res.stdout)
