"""Class upgrade goals of suits and weapons (ADR 0027, ADR 0030)."""

from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.domain.engineering.catalogue import OnFootKind
from edrockmaster.domain.engineering.goals import BlueprintGoal, ClassUpgradeGoal, GoalId
from edrockmaster.domain.engineering.journal import BlueprintApplied
from edrockmaster.domain.engineering.on_foot_journal import (
    LoadoutChosen,
    LockerStated,
    Stock,
    Suit,
    SuitBought,
    Weapon,
    WeaponBought,
    WeaponEquipped,
)
from edrockmaster.domain.engineering.session import (
    EngineeringNotification,
    EngineeringTracker,
    EngineeringUpdated,
    GoalDone,
    GoalProgress,
    GoalProgressed,
    GoalReady,
)
from tests.domain.engineering.catalogue_data import catalogue

T0 = datetime(2026, 10, 11, 1, 0, tzinfo=UTC)
DOMINATOR_ID = 1878707285049801
# The test catalogue knows the Dominator's upgrades to class 2 (read in game) and to class 3
# (deduced): chemical sample 1 and 2, graphene 2 and 5; 600,000 and 2,250,000 credits
TO_3 = ClassUpgradeGoal(GoalId("dominator"), "tacticalsuit", 1, 3, T0)
ECLIPSE = "wpn_m_submachinegun_laser_fauto"


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def locker(minutes: int = 0, mission: bool = False, **counts: int) -> LockerStated:
    kinds = {"chemicalsample": OnFootKind.ITEM, "graphene": OnFootKind.COMPONENT}
    return LockerStated(
        at(minutes),
        tuple(
            Stock(symbol, kinds[symbol], count, mission=mission) for symbol, count in counts.items()
        ),
    )


def suit(suit_class: int, suit_id: int = DOMINATOR_ID, symbol: str = "tacticalsuit") -> Suit:
    return Suit(suit_id, symbol, suit_class, ())


def wearing(piece: Suit, minutes: int = 5) -> LoadoutChosen:
    return LoadoutChosen(at(minutes), piece, ())


def progress_of(tracker: EngineeringTracker) -> GoalProgress:
    [progress] = tracker.stats().goals
    return progress


def of(kind: type, notifications: list[EngineeringNotification]) -> list[object]:
    return [n for n in notifications if isinstance(n, kind)]


@pytest.fixture
def tracker() -> EngineeringTracker:
    return EngineeringTracker(catalogue())


# What a goal takes


def test_a_goal_takes_every_step_and_its_credits(tracker: EngineeringTracker) -> None:
    tracker.add_goal(TO_3)
    progress = progress_of(tracker)
    assert progress.needed == {"chemicalsample": 3, "graphene": 7}
    assert progress.credits == 2_850_000
    assert progress.known
    # One step is deduced, not seen in game (ADR 0030)
    assert progress.unverified
    # Upgrades are bought at Pioneer Supplies: no engineer
    assert progress.engineers == ()
    # Missing is unknown until the game states the ship locker
    assert progress.missing is None
    assert not progress.ready


def test_a_goal_seen_in_game_only_is_verified(tracker: EngineeringTracker) -> None:
    tracker.add_goal(ClassUpgradeGoal(GoalId("to2"), "tacticalsuit", 1, 2, T0))
    assert not progress_of(tracker).unverified


def test_a_goal_misses_what_the_locker_and_backpack_lack(tracker: EngineeringTracker) -> None:
    tracker.add_goal(TO_3)
    tracker.handle(locker(chemicalsample=1, graphene=7))
    assert progress_of(tracker).missing == {"chemicalsample": 2}
    notifications = tracker.handle(locker(minutes=1, chemicalsample=3, graphene=7))
    assert of(GoalReady, notifications) == [GoalReady(TO_3)]
    assert progress_of(tracker).ready


def test_mission_items_do_not_count_towards_a_goal(tracker: EngineeringTracker) -> None:
    tracker.add_goal(TO_3)
    tracker.handle(locker(mission=True, chemicalsample=3, graphene=7))
    assert progress_of(tracker).missing == {"chemicalsample": 3, "graphene": 7}


def test_a_step_the_catalogue_does_not_know_leaves_the_goal_partly_known(
    tracker: EngineeringTracker,
) -> None:
    tracker.add_goal(ClassUpgradeGoal(GoalId("to4"), "tacticalsuit", 2, 4, T0))
    tracker.handle(locker(chemicalsample=9, graphene=9))
    progress = progress_of(tracker)
    # What is known is counted; the unknown step is said, and the goal is never ready
    assert progress.needed == {"chemicalsample": 2, "graphene": 5}
    assert progress.credits == 2_250_000
    assert progress.unknown_classes == (4,)
    assert not progress.known
    assert progress.missing == {}
    assert not progress.ready


def test_an_item_the_catalogue_does_not_know(tracker: EngineeringTracker) -> None:
    tracker.add_goal(ClassUpgradeGoal(GoalId("eclipse"), ECLIPSE, 1, 3, T0))
    progress = progress_of(tracker)
    assert progress.unknown_classes == (2, 3)
    assert progress.needed == {}
    assert progress.credits == 0


def test_the_on_foot_shopping_list_and_credits_add_up_every_goal(
    tracker: EngineeringTracker,
) -> None:
    tracker.add_goal(TO_3)
    tracker.add_goal(ClassUpgradeGoal(GoalId("other"), "tacticalsuit", 1, 2, T0))
    tracker.handle(locker(chemicalsample=2, graphene=20))
    assert tracker.on_foot_shopping_list() == {"chemicalsample": 2}
    assert tracker.on_foot_credits() == 3_450_000
    # The ship's shopping list holds the ship's materials only
    assert tracker.shopping_list() == {}


# When the journal shows the item


def test_the_player_s_item_rising_a_class_is_a_step_done(tracker: EngineeringTracker) -> None:
    goal = ClassUpgradeGoal(GoalId("mine"), "tacticalsuit", 1, 3, T0, DOMINATOR_ID)
    tracker.add_goal(goal)
    notifications = tracker.handle(wearing(suit(2)))
    after = ClassUpgradeGoal(GoalId("mine"), "tacticalsuit", 2, 3, T0, DOMINATOR_ID)
    assert of(GoalProgressed, notifications) == [GoalProgressed(after)]
    assert tracker.goals == (after,)
    assert progress_of(tracker).needed == {"chemicalsample": 2, "graphene": 5}
    [update] = of(EngineeringUpdated, notifications)
    assert isinstance(update, EngineeringUpdated)
    assert update.progressed


def test_the_player_s_item_at_the_class_aimed_at_is_the_goal_done(
    tracker: EngineeringTracker,
) -> None:
    goal = ClassUpgradeGoal(GoalId("mine"), "tacticalsuit", 1, 3, T0, DOMINATOR_ID)
    tracker.add_goal(goal)
    assert of(GoalDone, tracker.handle(SuitBought(at(5), suit(3)))) == [GoalDone(goal)]
    assert tracker.goals == ()


def test_a_goal_on_the_player_s_item_ignores_the_others(tracker: EngineeringTracker) -> None:
    tracker.add_goal(ClassUpgradeGoal(GoalId("mine"), "tacticalsuit", 1, 3, T0, DOMINATOR_ID))
    tracker.handle(wearing(suit(5, suit_id=42)))
    assert len(tracker.goals) == 1


def test_a_goal_on_a_type_counts_any_item_of_it_shown_after_it_was_set(
    tracker: EngineeringTracker,
) -> None:
    tracker.add_goal(TO_3)
    # Before the goal was set (the journal read from the start of the file), or another type
    tracker.handle(LoadoutChosen(at(-5), suit(3), ()))
    tracker.handle(wearing(suit(3, symbol="utilitysuit")))
    # A class not above the goal's start
    tracker.handle(wearing(suit(1)))
    assert tracker.goals == (TO_3,)
    assert of(GoalDone, tracker.handle(wearing(suit(4), minutes=6))) == [GoalDone(TO_3)]


def test_weapons_rise_the_same_way(tracker: EngineeringTracker) -> None:
    goal = ClassUpgradeGoal(GoalId("eclipse"), ECLIPSE, 1, 3, T0)
    tracker.add_goal(goal)
    tracker.handle(WeaponBought(at(1), Weapon(7, ECLIPSE, 2, ())))
    [progressed] = tracker.goals
    assert isinstance(progressed, ClassUpgradeGoal)
    assert progressed.from_class == 2
    done = tracker.handle(WeaponEquipped(at(2), Weapon(7, ECLIPSE, 3, ())))
    assert of(GoalDone, done) == [GoalDone(progressed)]


def test_the_flight_suit_has_no_class_and_moves_no_goal(tracker: EngineeringTracker) -> None:
    tracker.add_goal(TO_3)
    tracker.handle(wearing(Suit(3, "tacticalsuit", None, ())))
    assert tracker.goals == (TO_3,)


def test_a_ship_engineer_s_roll_leaves_class_upgrades_alone(tracker: EngineeringTracker) -> None:
    ship = BlueprintGoal(GoalId("range"), "FSD_LongRange", "fsd", grade=5)
    tracker.add_goal(TO_3)
    tracker.add_goal(ship)
    roll = BlueprintApplied(
        at(5), "FSD_LongRange", 5, "int_hyperdrive_size5_class5", 300100, None, ()
    )
    assert of(GoalDone, tracker.handle(roll)) == [GoalDone(ship)]
    assert tracker.goals == (TO_3,)
