"""Evidence frames: the exact video frame at a finding's timestamp (cached, extracted on demand)."""

from __future__ import annotations

from pathlib import Path

from fortnite_coach.video.frames import extract_frames


def evidence_frames(video: str, fingerprint: str, timestamps: list[float], frames_root: Path) -> dict[float, Path]:
    out_dir = frames_root / fingerprint[:16] / "evidence"
    result: dict[float, Path] = {}
    todo = []
    for t in timestamps:
        p = out_dir / f"ev_{int(t * 1000):09d}.jpg"
        if p.is_file():
            result[t] = p
        else:
            todo.append(t)
    if todo and Path(video).is_file():
        for t, p in zip(todo, extract_frames(video, todo, out_dir, max_width=384, prefix="tmp")):
            final = out_dir / f"ev_{int(t * 1000):09d}.jpg"
            p.replace(final)
            result[t] = final
    return result
