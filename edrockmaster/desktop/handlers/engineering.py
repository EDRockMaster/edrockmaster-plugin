"""The engineering goals' calls (ADR 0017, ADR 0033): the goal form, and the goals."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from edrockmaster.desktop.engineering_view import catalogue_view, goal_from_request, with_count
from edrockmaster.desktop.handlers.context import CoreContext
from edrockmaster.domain.engineering.goals import GoalId
from edrockmaster.ui.engineering_names import EngineeringNames


class EngineeringHandler:
    def __init__(self, context: CoreContext) -> None:
        self._context = context
        self._catalogue: tuple[str, dict[str, Any]] | None = None
        """The goal form's choices, and the language they are in."""

    def catalogue(self) -> dict[str, Any]:
        """What the goal form offers, built again only when the language changes. The catalogue
        never changes and the view is replaced, never changed: any thread."""
        language = self._context.language()
        if self._catalogue is None or self._catalogue[0] != language:
            catalogue = self._context.companion().engineering.catalogue
            view = catalogue_view(catalogue, EngineeringNames(catalogue, self._context.tl))
            self._catalogue = (language, view)
        return self._catalogue[1]

    def add_goal(self, request: Mapping[str, Any]) -> None:
        def add() -> None:
            engineering = self._context.companion().engineering
            try:
                goal = goal_from_request(
                    request,
                    engineering.catalogue,
                    engineering.equipment,
                    self._context.clock.now(),
                    engineering.engineers,
                )
            except ValueError as error:
                self._context.logger.warning("Goal refused: %s", error)
                return
            self._context.apply(engineering.add_goal(goal))

        self._context.on_core(add)

    def change_goal(self, goal_id: str, count: int) -> None:
        def change() -> None:
            engineering = self._context.companion().engineering
            goal = next((g for g in engineering.goals if g.id.value == goal_id), None)
            if goal is None:
                self._context.logger.warning("No goal %r to change", goal_id)
                return
            try:
                changed = with_count(goal, count)
            except (ValueError, TypeError) as error:
                self._context.logger.warning("Goal change refused: %s", error)
                return
            self._context.apply(engineering.replace_goal(changed))

        self._context.on_core(change)

    def remove_goal(self, goal_id: str) -> None:
        def remove() -> None:
            engineering = self._context.companion().engineering
            if not any(goal.id.value == goal_id for goal in engineering.goals):
                self._context.logger.warning("No goal %r to remove", goal_id)
                return
            self._context.apply(engineering.remove_goal(GoalId(goal_id)))

        self._context.on_core(remove)

    def order_goals(self, order: list[str]) -> None:
        """The player's priority (ADR 0033): the goals it names first, then the others."""

        def reorder() -> None:
            if not isinstance(order, list) or not all(isinstance(id_, str) for id_ in order):
                self._context.logger.warning("Goal order refused: %r", order)
                return
            engineering = self._context.companion().engineering
            self._context.apply(engineering.order_goals([GoalId(goal_id) for goal_id in order]))

        self._context.on_core(reorder)
