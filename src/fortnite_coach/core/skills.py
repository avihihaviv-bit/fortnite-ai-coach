"""The skills the coach evaluates."""

from __future__ import annotations

from enum import Enum


class Skill(str, Enum):
    BUILDING = "building"
    EDITING = "editing"
    PIECE_CONTROL = "piece_control"
    AIM = "aim"
    MOVEMENT = "movement"
    MECHANICS = "mechanics"
    GAME_SENSE = "game_sense"
    POSITIONING = "positioning"
    DECISION_MAKING = "decision_making"
    FIGHT_EXECUTION = "fight_execution"

    @property
    def i18n_key(self) -> str:
        return f"skill.{self.value}"


ALL_SKILLS: tuple[Skill, ...] = tuple(Skill)

# Skills that have their own page in the sidebar.
SKILL_PAGES: tuple[Skill, ...] = (
    Skill.BUILDING,
    Skill.EDITING,
    Skill.PIECE_CONTROL,
    Skill.AIM,
    Skill.GAME_SENSE,
)
