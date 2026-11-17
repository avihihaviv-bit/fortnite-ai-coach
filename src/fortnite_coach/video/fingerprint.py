"""Fast content fingerprint for duplicate detection and caching.

Hashing a multi-GB recording fully would be slow, so we hash the file size plus
the first, middle and last 4 MiB. Collisions between different real recordings
are practically impossible for this purpose.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK = 4 * 1024 * 1024


def fingerprint(path: str | Path) -> str:
    p = Path(path)
    size = p.stat().st_size
    h = hashlib.sha256(str(size).encode())
    with p.open("rb") as f:
        offsets = sorted({0, max(0, size // 2 - CHUNK // 2), max(0, size - CHUNK)})
        for off in offsets:
            f.seek(off)
            h.update(f.read(CHUNK))
    return h.hexdigest()
