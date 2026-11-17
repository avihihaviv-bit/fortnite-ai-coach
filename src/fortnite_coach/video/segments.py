"""Split long videos into analysis segments and report coverage honestly."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    index: int
    start_s: float
    end_s: float
    analyzed: bool  # False = beyond the configured limit; shown to the user as "not analyzed"

    @property
    def length_s(self) -> float:
        return self.end_s - self.start_s


def plan_segments(duration_s: float, segment_s: float, max_analyzed_s: float) -> list[Segment]:
    if duration_s <= 0 or segment_s <= 0:
        return []
    segs: list[Segment] = []
    start, i, budget = 0.0, 0, max_analyzed_s
    while start < duration_s - 0.01:
        end = min(duration_s, start + segment_s)
        length = end - start
        analyzed = budget >= length - 0.01
        if analyzed:
            budget -= length
        else:
            budget = 0.0  # coverage is one continuous block from the start; no gaps
        segs.append(Segment(i, round(start, 3), round(end, 3), analyzed))
        start, i = end, i + 1
    return segs


def coverage(segs: list[Segment]) -> tuple[float, float]:
    """(analyzed seconds, total seconds)."""
    total = sum(s.length_s for s in segs)
    return round(sum(s.length_s for s in segs if s.analyzed), 3), round(total, 3)
