"""Frame extraction with OpenCV (thumbnails now, analysis sampling later)."""

from __future__ import annotations

from pathlib import Path

import cv2

from fortnite_coach.core.errors import VideoError


def even_timestamps(duration_s: float, count: int) -> list[float]:
    """`count` timestamps spread evenly, avoiding the very first/last frame."""
    if count <= 0 or duration_s <= 0:
        return []
    step = duration_s / (count + 1)
    return [round(step * (i + 1), 3) for i in range(count)]


def extract_frames(
    video: str | Path, timestamps: list[float], out_dir: Path, *, max_width: int = 640, prefix: str = "frame"
) -> list[Path]:
    """Save JPEG frames at the given timestamps. The capture is always released."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise VideoError("opencv could not open", i18n_key="video.err_unreadable")
    saved: list[Path] = []
    try:
        for i, t in enumerate(timestamps):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok:
                continue
            h, w = frame.shape[:2]
            if w > max_width:
                frame = cv2.resize(frame, (max_width, int(h * max_width / w)), interpolation=cv2.INTER_AREA)
            path = out_dir / f"{prefix}_{i:03d}_{int(t * 1000):09d}.jpg"
            if cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85]):
                saved.append(path)
    finally:
        cap.release()
    return saved
