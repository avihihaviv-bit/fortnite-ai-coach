"""Structured response schema sent to Gemini (`response_schema`) for ONE video segment.

Kept to plain types so the Gemini schema converter accepts it; all value checks
(ranges, known codes, timestamps inside the segment) happen in gemini_response_parser.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MistakeOut(BaseModel):
    code: str = Field(description="One of the allowed mistake codes, or OTHER")
    skill: str
    severity: str = Field(description="low, medium or high")
    start: str = Field(description="Absolute video time MM:SS where it starts")
    end: str = Field(description="Absolute video time MM:SS where it ends")
    what_happened: str = Field(description="What the player did, concretely")
    better_option: str = Field(description="What would have been better")
    why: str = Field(description="Why the better option is better")
    how_to_practice: str = Field(description="A specific drill to fix it")
    evidence: str = Field(description="What is visible in the video that shows this")
    confidence: float = Field(description="0 to 1")
    search_query: str = Field(default="", description=(
        "English search phrase, 4-9 words, that this player should type on YouTube / TikTok / Google to find a "
        "tutorial fixing exactly THIS situation (name the mechanic, the mode and the moment), e.g. "
        "'fortnite how to protect while healing in box fights' or 'fortnite pre fire double edit tutorial'"))


class GoodPlayOut(BaseModel):
    code: str = Field(description="One of the allowed good-play codes, or OTHER")
    skill: str
    difficulty: str = Field(description="easy, medium or hard")
    start: str
    end: str
    what_happened: str
    evidence: str
    confidence: float


class SkillAssessmentOut(BaseModel):
    skill: str
    score: int | None = Field(default=None, description="0-100, or null if not enough evidence in this segment")
    evidence_count: int = Field(description="How many observed moments support the score")
    confidence: float
    rationale: str


class StatsOut(BaseModel):
    """Counts the model can make from the video itself. null = could not be counted reliably."""

    shots_fired: int | None = Field(default=None, description=(
        "Shots fired by the player in this segment (firing animation, muzzle flash, ammo dropping or the "
        "player's gunshot sound). null if you cannot count them reliably"))
    shots_hit: int | None = Field(default=None, description=(
        "Of those, shots that visibly hit an opponent (hit marker or damage number). null if unsure"))
    headshots: int | None = Field(default=None, description=(
        "Of the hits, headshots: the damage number is yellow/gold (body hits are white). null if unsure"))
    edits_attempted: int | None = Field(default=None, description="Edits started (edit grid/outline shown)")
    edits_completed: int | None = Field(default=None, description="Edits that actually opened/changed the piece")
    fights: int | None = Field(default=None, description="Fights with an opponent in this segment")
    fights_won: int | None = Field(default=None, description="Fights the player clearly won (opponent knocked/eliminated)")
    eliminations: int | None = Field(default=None, description="Eliminations/knocks by the player (kill feed / notice)")
    times_eliminated: int | None = Field(default=None, description="Times the player was knocked or eliminated")


class SegmentResult(BaseModel):
    segment_summary: str
    mistakes: list[MistakeOut] = Field(default_factory=list)
    good_plays: list[GoodPlayOut] = Field(default_factory=list)
    skill_assessments: list[SkillAssessmentOut] = Field(default_factory=list)
    not_determinable: list[str] = Field(default_factory=list, description="Things that could not be judged from the video")
    stats: StatsOut | None = Field(default=None, description="Counts from this segment; null fields when not countable")
