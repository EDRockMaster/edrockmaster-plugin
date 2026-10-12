"""What the engineering context tells the application layer after each change."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from edrockmaster.domain.engineering.collection import CollectionEndReason, CollectionStats
from edrockmaster.domain.engineering.goals import Goal
from edrockmaster.domain.engineering.progress import GoalProgress


@dataclass(frozen=True, slots=True)
class EngineeringStats:
    collection: CollectionStats | None
    goals: tuple[GoalProgress, ...]
    inventory_known: bool

    @property
    def goals_ready(self) -> int:
        return sum(1 for progress in self.goals if progress.ready)


@dataclass(frozen=True, slots=True)
class CollectionStarted:
    at: datetime


@dataclass(frozen=True, slots=True)
class CollectionEnded:
    at: datetime
    reason: CollectionEndReason


@dataclass(frozen=True, slots=True)
class EngineeringUpdated:
    stats: EngineeringStats
    progressed: bool
    """A change the player made in game (not a statement of the game at load)."""


@dataclass(frozen=True, slots=True)
class MaterialCapped:
    symbol: str
    name: str | None
    cap: int


@dataclass(frozen=True, slots=True)
class GoalReady:
    goal: Goal


@dataclass(frozen=True, slots=True)
class GoalProgressed:
    """A roll or an application was made: the goal has one fewer."""

    goal: Goal


@dataclass(frozen=True, slots=True)
class GoalDone:
    goal: Goal


type EngineeringNotification = (
    CollectionStarted
    | CollectionEnded
    | EngineeringUpdated
    | MaterialCapped
    | GoalReady
    | GoalProgressed
    | GoalDone
)
