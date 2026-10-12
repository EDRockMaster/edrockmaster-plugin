"""Modification goals of suits and weapons (ADR 0027, ADR 0030)."""

from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.domain.engineering.catalogue import OnFootKind
from edrockmaster.domain.engineering.events import EngineeringNotification, GoalDone, GoalReady
from edrockmaster.domain.engineering.goals import ClassUpgradeGoal, GoalId, ModificationGoal
from edrockmaster.domain.engineering.journal import (
    EngineersStated,
    EngineerState,
    EngineerStatus,
)
from edrockmaster.domain.engineering.on_foot_journal import (
    LoadoutChosen,
    LockerStated,
    Stock,
    Suit,
    Weapon,
    WeaponEquipped,
)
from edrockmaster.domain.engineering.progress import GoalProgress
from edrockmaster.domain.engineering.session import EngineeringTracker
from tests.domain.engineering.catalogue_data import catalogue

T0 = datetime(2026, 10, 11, 1, 0, tzinfo=UTC)
DOMINATOR_ID = 1878707285049801
DOMINO_GREEN = 400002
BACKPACK = "suit_backpackcapacity"
# The test catalogue knows this modification on the Dominator: 750,000 credits, graphene 3 and
# internal correspondence 5, offered by Domino Green
GOAL = ModificationGoal(GoalId("backpack"), "tacticalsuit", BACKPACK, T0)
ECLIPSE = "wpn_m_submachinegun_laser_fauto"


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def locker(minutes: int = 0, **counts: int) -> LockerStated:
    kinds = {
        "graphene": OnFootKind.COMPONENT,
        "internalcorrespondence": OnFootKind.DATA,
        "chemicalsample": OnFootKind.ITEM,
    }
    return LockerStated(
        at(minutes), tuple(Stock(symbol, kinds[symbol], count) for symbol, count in counts.items())
    )


def wearing(
    mods: tuple[str, ...],
    minutes: int = 5,
    suit_id: int = DOMINATOR_ID,
    symbol: str = "tacticalsuit",
) -> LoadoutChosen:
    return LoadoutChosen(at(minutes), Suit(suit_id, symbol, 3, mods), ())


def progress_of(tracker: EngineeringTracker) -> GoalProgress:
    [progress] = tracker.stats().goals
    return progress


def of(kind: type, notifications: list[EngineeringNotification]) -> list[object]:
    return [n for n in notifications if isinstance(n, kind)]


@pytest.fixture
def tracker() -> EngineeringTracker:
    return EngineeringTracker(catalogue())


# What a goal takes


def test_a_goal_takes_its_recipe_and_credits(tracker: EngineeringTracker) -> None:
    tracker.add_goal(GOAL)
    progress = progress_of(tracker)
    assert progress.needed == {"graphene": 3, "internalcorrespondence": 5}
    assert progress.credits == 750_000
    assert progress.known
    assert not progress.unverified
    assert progress.missing is None
    tracker.handle(locker(graphene=3, internalcorrespondence=1))
    assert progress_of(tracker).missing == {"internalcorrespondence": 4}
    notifications = tracker.handle(locker(minutes=1, graphene=3, internalcorrespondence=5))
    assert of(GoalReady, notifications) == [GoalReady(GOAL)]


def test_the_engineers_offering_it_once_unlocked(tracker: EngineeringTracker) -> None:
    tracker.add_goal(GOAL)
    assert progress_of(tracker).engineers == ()
    state = EngineerState(DOMINO_GREEN, "Domino Green", EngineerStatus.UNLOCKED, None)
    tracker.handle(EngineersStated(T0, (state,)))
    assert progress_of(tracker).engineers == (DOMINO_GREEN,)


def test_a_recipe_not_read_on_the_item_type_leaves_the_goal_unknown(
    tracker: EngineeringTracker,
) -> None:
    tracker.add_goal(ModificationGoal(GoalId("maverick"), "utilitysuit", BACKPACK, T0))
    tracker.handle(locker(graphene=9))
    progress = progress_of(tracker)
    assert not progress.known
    assert progress.needed == {}
    assert progress.credits == 0
    assert not progress.ready


def test_a_modification_the_catalogue_does_not_know(tracker: EngineeringTracker) -> None:
    tracker.add_goal(ModificationGoal(GoalId("scope"), ECLIPSE, "weapon_scope", T0))
    assert not progress_of(tracker).known


def test_the_on_foot_shopping_list_and_credits_count_modifications_and_upgrades(
    tracker: EngineeringTracker,
) -> None:
    tracker.add_goal(GOAL)
    tracker.add_goal(ClassUpgradeGoal(GoalId("to2"), "tacticalsuit", 1, 2, T0))
    tracker.handle(locker(graphene=4, chemicalsample=1))
    assert tracker.on_foot_shopping_list() == {"graphene": 1, "internalcorrespondence": 5}
    assert tracker.on_foot_credits() == 1_350_000
    assert tracker.shopping_list() == {}


# When the journal shows the item


def test_the_player_s_item_showing_the_modification_is_the_goal_done(
    tracker: EngineeringTracker,
) -> None:
    goal = ModificationGoal(GoalId("mine"), "tacticalsuit", BACKPACK, T0, DOMINATOR_ID)
    tracker.add_goal(goal)
    assert of(GoalDone, tracker.handle(wearing(("suit_nightvision",)))) == []
    tracker.handle(wearing((BACKPACK,), suit_id=42))
    assert tracker.goals == (goal,)
    assert of(GoalDone, tracker.handle(wearing(("suit_nightvision", BACKPACK)))) == [GoalDone(goal)]
    assert not tracker.goals


def test_a_goal_on_a_type_counts_any_item_of_it_shown_after_it_was_set(
    tracker: EngineeringTracker,
) -> None:
    tracker.add_goal(GOAL)
    tracker.handle(wearing((BACKPACK,), minutes=-5))
    tracker.handle(wearing((BACKPACK,), symbol="utilitysuit"))
    assert tracker.goals == (GOAL,)
    assert of(GoalDone, tracker.handle(wearing((BACKPACK,), minutes=6))) == [GoalDone(GOAL)]


def test_weapons_are_modified_the_same_way(tracker: EngineeringTracker) -> None:
    goal = ModificationGoal(GoalId("handling"), ECLIPSE, "weapon_handling", T0, 7)
    tracker.add_goal(goal)
    done = tracker.handle(WeaponEquipped(at(2), Weapon(7, ECLIPSE, 3, ("weapon_handling",))))
    assert of(GoalDone, done) == [GoalDone(goal)]


def test_a_class_upgrade_does_not_complete_a_modification(tracker: EngineeringTracker) -> None:
    upgrade = ClassUpgradeGoal(GoalId("to2"), "tacticalsuit", 1, 2, T0, DOMINATOR_ID)
    goal = ModificationGoal(GoalId("mine"), "tacticalsuit", BACKPACK, T0, DOMINATOR_ID)
    tracker.add_goal(upgrade)
    tracker.add_goal(goal)
    assert of(GoalDone, tracker.handle(wearing(()))) == [GoalDone(upgrade)]
    assert tracker.goals == (goal,)
