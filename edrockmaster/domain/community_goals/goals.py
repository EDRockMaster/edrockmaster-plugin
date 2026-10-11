"""The community goals the commander has joined (ADR 0032).

``CommunityGoals`` is the aggregate root of the context. The game states the
whole list at load and every few minutes near a goal; a goal goes with that
list, or with its reward or its discard, after which the game writes no new
list. It is not a session: nothing starts, nothing is reset.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import assert_never

from edrockmaster.domain.community_goals.journal import (
    CommunityGoal,
    CommunityGoalLeft,
    CommunityGoalsUpdated,
    Fact,
)


@dataclass(frozen=True, slots=True)
class CommunityGoalsChanged:
    goals: tuple[CommunityGoal, ...]


type CommunityGoalsNotification = CommunityGoalsChanged


class CommunityGoals:
    def __init__(self) -> None:
        self._goals: tuple[CommunityGoal, ...] = ()

    @property
    def goals(self) -> tuple[CommunityGoal, ...]:
        return self._goals

    def handle(self, fact: Fact) -> list[CommunityGoalsNotification]:
        match fact:
            case CommunityGoalsUpdated(goals=goals):
                return self._change(goals)
            case CommunityGoalLeft(cgid=cgid):
                return self._change(tuple(goal for goal in self._goals if goal.cgid != cgid))
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(fact)

    def _change(self, goals: tuple[CommunityGoal, ...]) -> list[CommunityGoalsNotification]:
        if goals == self._goals:
            return []
        self._goals = goals
        return [CommunityGoalsChanged(goals)]
