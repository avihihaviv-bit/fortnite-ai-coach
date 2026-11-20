"""Join the parts of one recording into a single video. Runs only when the user clicks
"Load this recording" (after the game), on a worker thread.

- 1 part: renamed to the final name.
- same resolution and codec: ffmpeg concat with stream copy (fast, no quality loss).
- different resolutions (the game changed resolution mid-recording): re-encoded to the
  most common size.
Parts are deleted only after the joined file has been verified with ffprobe.
"""

from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path

from fortnite_coach.core.errors import VideoError
from fortnite_coach.video.ffmpeg_tools import find_ffmpeg, find_ffprobe, run
from fortnite_coach.video.metadata import VideoMetadata, probe


def final_name(parts: list[Path]) -> Path:
    first = parts[0]
    stem = first.stem.rsplit("_part", 1)[0]
    return first.with_name(f"{stem}.mp4")


def _verify(path: Path, ffprobe: str) -> VideoMetadata:
    meta = probe(path, ffprobe)
    if meta.duration_s <= 0:
        raise VideoError("merged file has no duration", i18n_key="video.err_merge")
    return meta


def merge_parts(parts: list[str | Path], *, ffmpeg: str | None = None, ffprobe: str | None = None) -> Path:
    paths = [Path(p) for p in parts if Path(p).is_file()]
    if not paths:
        raise VideoError("no parts", i18n_key="video.err_missing")
    ffmpeg, ffprobe = find_ffmpeg(ffmpeg), find_ffprobe(ffprobe)
    metas = []
    for p in paths:  # skip a damaged last part instead of failing the whole recording
        try:
            metas.append((p, probe(p, ffprobe)))
        except VideoError:
            continue
    if not metas:
        raise VideoError("no readable part", i18n_key="video.err_unreadable")
    out = final_name([p for p, _ in metas])
    if out.exists():
        out = out.with_name(f"{out.stem}_joined.mp4")
    if len(metas) == 1:
        metas[0][0].replace(out)
        return out

    tmp = out.with_suffix(".joining.mp4")
    sizes = Counter((m.width, m.height) for _, m in metas)
    same = len(sizes) == 1 and len({m.codec for _, m in metas}) == 1
    try:
        if same:
            listing = out.with_suffix(".parts.txt")
            listing.write_text("".join("file '{}'\n".format(str(p).replace("'", "'\\''")) for p, _ in metas),
                               encoding="utf-8")
            args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(tmp)]
        else:
            (w, h), _n = sizes.most_common(1)[0]
            with_audio = all(m.has_audio for _, m in metas)
            args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
            for p, _ in metas:
                args += ["-i", str(p)]
            chains, labels = [], []
            for i in range(len(metas)):
                chains.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                              f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}]")
                labels.append(f"[v{i}]" + (f"[{i}:a]" if with_audio else ""))
            concat = "".join(labels) + f"concat=n={len(metas)}:v=1:a={1 if with_audio else 0}[v]" + ("[a]" if with_audio else "")
            args += ["-filter_complex", ";".join(chains + [concat]), "-map", "[v]"]
            if with_audio:
                args += ["-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
            args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                     "-movflags", "+faststart", str(tmp)]
        res = run(args, timeout=3600)
        if res.returncode != 0 or not tmp.is_file():
            raise VideoError(res.stderr[-300:], i18n_key="video.err_merge")
        _verify(tmp, ffprobe)
        tmp.replace(out)
    except (subprocess.TimeoutExpired, OSError) as e:
        raise VideoError(str(e), i18n_key="video.err_merge") from e
    finally:
        tmp.unlink(missing_ok=True)
        out.with_suffix(".parts.txt").unlink(missing_ok=True)
    for p, _ in metas:  # only now, after the joined file was verified
        p.unlink(missing_ok=True)
    return out
