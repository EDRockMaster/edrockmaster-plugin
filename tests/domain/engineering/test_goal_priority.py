"""The goals' priority: the materials held go to the goals in the player's order (ADR 0033)."""

from datetime import UTC, datetime

import pytest

from edrockmaster.domain.engineering.catalogue import OnFootKind
from edrockmaster.domain.engineering.goals import (
    BlueprintGoal,
    ExperimentalEffectGoal,
    GoalId,
    ModificationGoal,
)
from edrockmaster.domain.engineering.journal import InventoryStated, MaterialChange
from edrockmaster.domain.engineering.on_foot_journal import LockerStated, Stock
from edrockmaster.domain.engineering.session import (
    EngineeringTracker,
    EngineeringUpdated,
    GoalProgress,
    GoalReady,
)
from tests.domain.engineering.catalogue_data import catalogue

T0 = datetime(2026, 10, 11, 14, 0, tzinfo=UTC)
# Two rolls: arsenic 2, chemical manipulators 2, datamined wake 2
RANGE = BlueprintGoal(GoalId("range"), "FSD_LongRange", "fsd", grade=5, rolls=2)
# Arsenic 5, datamined wake 3
MASS_MANAGER = ExperimentalEffectGoal(GoalId("mass"), "special_fsd_heavy", "fsd")
UNKNOWN = BlueprintGoal(GoalId("unknown"), "Nothing_Known", "fsd", grade=5)
# Graphene 3, internal correspondence 5 each
BACKPACK = ModificationGoal(GoalId("backpack"), "tacticalsuit", "suit_backpackcapacity", T0)
BACKPACK_AGAIN = ModificationGoal(GoalId("again"), "tacticalsuit", "suit_backpackcapacity", T0)


def held(**counts: int) -> InventoryStated:
    return InventoryStated(
        T0, tuple(MaterialChange(symbol, count) for symbol, count in counts.items())
    )


def locker(**counts: int) -> LockerStated:
    kinds = {"graphene": OnFootKind.COMPONENT, "internalcorrespondence": OnFootKind.DATA}
    return LockerStated(
        T0, tuple(Stock(symbol, kinds[symbol], count) for symbol, count in counts.items())
    )


def progress(tracker: EngineeringTracker) -> dict[str, GoalProgress]:
    return {p.goal.id.value: p for p in tracker.stats().goals}


@pytest.fixture
def tracker() -> EngineeringTracker:
    tracker = EngineeringTracker(catalogue())
    # Enough for either goal alone, not for both: arsenic 2 + 5 > 5
    tracker.handle(held(arsenic=5, chemicalmanipulators=2, dataminedwake=3))
    return tracker


def test_the_first_goal_takes_the_materials_both_need(tracker: EngineeringTracker) -> None:
    tracker.add_goal(RANGE)
    tracker.add_goal(MASS_MANAGER)
    goals = progress(tracker)
    assert goals["range"].ready
    assert goals["mass"].missing == {"arsenic": 2, "dataminedwake": 2}
    assert not goals["mass"].ready
    assert goals["mass"].ready_alone  # "taken by a goal above"
    assert tracker.stats().goals_ready == 1


def test_swapping_the_goals_swaps_which_one_is_ready(tracker: EngineeringTracker) -> None:
    tracker.add_goal(RANGE)
    tracker.add_goal(MASS_MANAGER)
    shopping = tracker.shopping_list()
    tracker.order_goals([MASS_MANAGER.id, RANGE.id])
    goals = progress(tracker)
    assert goals["mass"].ready
    assert goals["range"].missing == {"arsenic": 2, "dataminedwake": 2}
    assert goals["range"].ready_alone
    # The shopping list does not depend on the order
    assert tracker.shopping_list() == shopping


def test_a_goal_that_cannot_be_completed_still_puts_materials_aside(
    tracker: EngineeringTracker,
) -> None:
    tracker.handle(held(arsenic=5, dataminedwake=3))  # no chemical manipulators
    tracker.add_goal(RANGE)
    tracker.add_goal(MASS_MANAGER)
    goals = progress(tracker)
    assert goals["range"].missing == {"chemicalmanipulators": 2}
    assert goals["mass"].missing == {"arsenic": 2, "dataminedwake": 2}


def test_a_goal_ready_alone_and_after_the_goals_above_is_ready(
    tracker: EngineeringTracker,
) -> None:
    tracker.add_goal(MASS_MANAGER)
    goals = progress(tracker)
    assert goals["mass"].ready
    assert goals["mass"].ready_alone


def test_a_goal_the_catalogue_does_not_know_takes_nothing(tracker: EngineeringTracker) -> None:
    tracker.add_goal(UNKNOWN)
    tracker.add_goal(MASS_MANAGER)
    assert progress(tracker)["mass"].ready


def test_ship_and_on_foot_materials_are_reserved_apart(tracker: EngineeringTracker) -> None:
    tracker.handle(locker(graphene=3, internalcorrespondence=5))
    for goal in (RANGE, BACKPACK, MASS_MANAGER, BACKPACK_AGAIN):
        tracker.add_goal(goal)
    goals = progress(tracker)
    assert [goals[key].ready for key in ("range", "backpack", "mass", "again")] == [
        True,
        True,
        False,
        False,
    ]
    assert goals["again"].missing == {"graphene": 3, "internalcorrespondence": 5}
    assert goals["again"].ready_alone


def test_raising_a_goal_makes_it_ready(tracker: EngineeringTracker) -> None:
    tracker.add_goal(RANGE)
    tracker.add_goal(MASS_MANAGER)
    notifications = tracker.order_goals([MASS_MANAGER.id, RANGE.id])
    assert GoalReady(MASS_MANAGER) in notifications
    [update] = [n for n in notifications if isinstance(n, EngineeringUpdated)]
    assert update.stats.goals_ready == 1


def test_an_order_keeps_the_goals_it_does_not_name_after_those_it_names(
    tracker: EngineeringTracker,
) -> None:
    for goal in (RANGE, MASS_MANAGER, UNKNOWN):
        tracker.add_goal(goal)
    tracker.order_goals([UNKNOWN.id, GoalId("gone"), RANGE.id])
    assert tracker.goals == (UNKNOWN, RANGE, MASS_MANAGER)


def test_a_new_goal_comes_last(tracker: EngineeringTracker) -> None:
    tracker.add_goal(MASS_MANAGER)
    tracker.add_goal(RANGE)
    assert tracker.goals == (MASS_MANAGER, RANGE)
    assert not progress(tracker)["range"].ready
