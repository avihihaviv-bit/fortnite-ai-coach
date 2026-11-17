"""Create a small analysis copy of the video (only the part that will be analyzed).

Uploading a 2 GB 1440p recording would waste time and quota; Gemini samples ~1 frame/s
anyway, so a compressed 720p/1080p copy carries the same information.
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

from fortnite_coach.core.errors import OperationCancelledError, VideoError
from fortnite_coach.video.ffmpeg_tools import NO_WINDOW


def proxy_path(cache_dir: Path, fingerprint: str, height: int, seconds: float) -> Path:
    return cache_dir / f"{fingerprint[:16]}_{height}p_{int(seconds)}s.mp4"


def make_proxy(ffmpeg: str, src: Path, out: Path, *, height: int, max_seconds: float,
               cancel: threading.Event | None = None, timeout_s: float = 1800) -> Path:
    if out.is_file() and out.stat().st_size > 0:
        return out  # reuse
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part.mp4")
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-t", f"{max_seconds:.3f}",
            "-vf", f"scale=-2:'min({height},ih)'", "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "28", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "1", "-b:a", "64k",
            "-movflags", "+faststart", str(tmp)]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=NO_WINDOW)
    waited = 0.0
    try:
        while proc.poll() is None:
            if cancel is not None and cancel.is_set():
                proc.kill()
                raise OperationCancelledError()
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                waited += 0.5
                if waited > timeout_s:
                    proc.kill()
                    raise VideoError("proxy timeout", i18n_key="video.err_proxy")
        if proc.returncode != 0 or not tmp.is_file():
            err = (proc.stderr.read() if proc.stderr else b"").decode(errors="replace")[-300:]
            raise VideoError(err, i18n_key="video.err_proxy")
        tmp.replace(out)
        return out
    finally:
        if proc.stderr:
            proc.stderr.close()
        if tmp.exists() and not out.exists():
            tmp.unlink(missing_ok=True)
