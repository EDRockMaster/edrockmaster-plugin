"""Use cases of engineering (ADR 0017, ADR 0027): the journal, the player's goals, their storage."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence

from edrockmaster.application.ports import Clock, GoalRepository
from edrockmaster.domain.engineering.catalogue import Catalogue, Ingredients
from edrockmaster.domain.engineering.goals import Goal, GoalId
from edrockmaster.domain.engineering.journal import EngineerState, Fact, parse_entry
from edrockmaster.domain.engineering.on_foot import CarrierMove, Equipment, OnFootHolding
from edrockmaster.domain.engineering.session import (
    CollectionEndReason,
    EngineeringNotification,
    EngineeringStats,
    EngineeringTracker,
    GoalDone,
    GoalProgressed,
)
from edrockmaster.domain.journal_reading import Entry

type Publish = Callable[[Sequence[EngineeringNotification]], object]


class EngineeringService:
    """Called on the core thread only; the goals are stored through a non-blocking port."""

    def __init__(self, catalogue: Catalogue, goals: GoalRepository, clock: Clock) -> None:
        self._tracker = EngineeringTracker(catalogue)
        self._goals = goals
        self._clock = clock

    # Queries, for the panel and the window

    @property
    def catalogue(self) -> Catalogue:
        return self._tracker.catalogue

    @property
    def stats(self) -> EngineeringStats:
        return self._tracker.stats()

    @property
    def inventory(self) -> Mapping[str, int] | None:
        return self._tracker.inventory

    @property
    def engineers(self) -> Mapping[int, EngineerState]:
        return self._tracker.engineers

    @property
    def goals(self) -> tuple[Goal, ...]:
        return self._tracker.goals

    def shopping_list(self) -> Ingredients:
        return self._tracker.shopping_list()

    @property
    def on_foot_inventory(self) -> tuple[OnFootHolding, ...] | None:
        return self._tracker.on_foot_inventory

    def on_foot_held(self) -> Mapping[str, int]:
        return self._tracker.on_foot_held()

    @property
    def equipment(self) -> Mapping[int, Equipment]:
        return self._tracker.equipment

    @property
    def carrier_moves(self) -> tuple[CarrierMove, ...]:
        return self._tracker.carrier_moves

    def name_of(self, symbol: str) -> str | None:
        return self._tracker.name_of(symbol)

    # The journal

    def handle_journal_entry(self, entry: Entry) -> list[EngineeringNotification]:
        fact = parse_entry(entry)
        return self.handle(fact) if fact is not None else []

    def handle(self, fact: Fact) -> list[EngineeringNotification]:
        """A fact of the journal."""
        return self._stored(self._tracker.handle(fact))

    def reset_session(self) -> list[EngineeringNotification]:
        return self._tracker.end(self._clock.now(), CollectionEndReason.MANUAL)

    # The player's goals

    def load_goals(self, publish: Publish) -> None:
        """Read the stored goals; ``publish`` receives the update later, on the main thread."""

        def loaded(goals: tuple[Goal, ...]) -> None:
            publish(self._tracker.load_goals(goals))

        self._goals.load(loaded)

    def add_goal(self, goal: Goal) -> list[EngineeringNotification]:
        self._goals.add(goal)
        return self._tracker.add_goal(goal)

    def replace_goal(self, goal: Goal) -> list[EngineeringNotification]:
        self._goals.replace(goal)
        return self._tracker.replace_goal(goal)

    def remove_goal(self, goal_id: GoalId) -> list[EngineeringNotification]:
        self._goals.remove(goal_id)
        return self._tracker.remove_goal(goal_id)

    def _stored(
        self, notifications: Iterable[EngineeringNotification]
    ) -> list[EngineeringNotification]:
        """Store the goals the journal changed (a roll made, a goal done)."""
        notifications = list(notifications)
        for notification in notifications:
            if isinstance(notification, GoalProgressed):
                self._goals.replace(notification.goal)
            elif isinstance(notification, GoalDone):
                self._goals.remove(notification.goal.id)
        return notifications
