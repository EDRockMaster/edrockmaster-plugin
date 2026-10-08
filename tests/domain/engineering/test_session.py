from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.domain.engineering.catalogue import MaterialCategory
from edrockmaster.domain.engineering.goals import BlueprintGoal, ExperimentalEffectGoal, GoalId
from edrockmaster.domain.engineering.journal import (
    BlueprintApplied,
    ChangeCause,
    EngineerProgressed,
    EngineersStated,
    EngineerState,
    EngineerStatus,
    GameClosed,
    InventoryStated,
    MaterialChange,
    MaterialsChanged,
)
from edrockmaster.domain.engineering.session import (
    CollectionEnded,
    CollectionEndReason,
    CollectionStarted,
    EngineeringNotification,
    EngineeringTracker,
    EngineeringUpdated,
    GoalDone,
    GoalProgressed,
    GoalReady,
    MaterialCapped,
)
from tests.domain.engineering.catalogue_data import catalogue

T0 = datetime(2026, 10, 8, 4, 0, tzinfo=UTC)
FARSEER = 300100
RANGE = BlueprintGoal(GoalId("range"), "FSD_LongRange", "fsd", grade=5, rolls=2)
MASS_MANAGER = ExperimentalEffectGoal(GoalId("mass"), "special_fsd_heavy", "fsd")
FSD = "int_hyperdrive_size5_class5"


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def held(**counts: int) -> InventoryStated:
    return InventoryStated(
        T0, tuple(MaterialChange(symbol, count) for symbol, count in counts.items())
    )


def collected(symbol: str, count: int, minutes: int = 1) -> MaterialsChanged:
    return MaterialsChanged(at(minutes), ChangeCause.COLLECTED, (MaterialChange(symbol, count),))


def rolled(goal_grade: int = 5, item: str = FSD, effect: str | None = None) -> BlueprintApplied:
    spent = (
        MaterialChange("arsenic", -1),
        MaterialChange("chemicalmanipulators", -1),
        MaterialChange("dataminedwake", -1),
    )
    return BlueprintApplied(at(5), "FSD_LongRange", goal_grade, item, FARSEER, effect, spent)


def unlocked(*ids: int) -> EngineersStated:
    return EngineersStated(
        T0, tuple(EngineerState(id_, f"engineer {id_}", EngineerStatus.UNLOCKED, 5) for id_ in ids)
    )


def updates(notifications: list[EngineeringNotification]) -> list[EngineeringUpdated]:
    return [n for n in notifications if isinstance(n, EngineeringUpdated)]


@pytest.fixture
def tracker() -> EngineeringTracker:
    return EngineeringTracker(catalogue())


# Inventory


def test_the_inventory_is_unknown_until_the_game_states_it(tracker: EngineeringTracker) -> None:
    tracker.handle(collected("arsenic", 3))
    assert tracker.inventory is None
    [update] = updates(tracker.handle(held(arsenic=10)))
    assert not update.progressed  # the game's statement at load is no progress
    assert tracker.inventory == {"arsenic": 10}
    tracker.handle(collected("arsenic", 3))
    assert tracker.inventory == {"arsenic": 13}


def test_a_material_reaching_its_cap_is_reported_and_kept_at_it(
    tracker: EngineeringTracker,
) -> None:
    tracker.handle(held(arsenic=245))  # grade 2: 250
    notifications = tracker.handle(collected("arsenic", 9))
    assert MaterialCapped("arsenic", None, 250) in notifications
    assert tracker.inventory == {"arsenic": 250}
    # Already at its cap: lost, not reported again
    assert not any(isinstance(n, MaterialCapped) for n in tracker.handle(collected("arsenic", 3)))
    stats = tracker.stats().collection
    assert stats is not None
    assert stats.capped == ("arsenic",)


def test_a_material_capped_again_is_listed_once(tracker: EngineeringTracker) -> None:
    tracker.handle(held(arsenic=249))
    tracker.handle(collected("arsenic", 3))
    tracker.handle(MaterialsChanged(at(2), ChangeCause.DISCARDED, (MaterialChange("arsenic", -9),)))
    assert any(isinstance(n, MaterialCapped) for n in tracker.handle(collected("arsenic", 9, 3)))
    stats = tracker.stats().collection
    assert stats is not None
    assert stats.capped == ("arsenic",)


def test_the_tracker_reads_its_catalogue(tracker: EngineeringTracker) -> None:
    assert "arsenic" in tracker.catalogue.materials


def test_a_count_never_goes_below_zero(tracker: EngineeringTracker) -> None:
    tracker.handle(held(arsenic=2))
    tracker.handle(MaterialsChanged(at(1), ChangeCause.DISCARDED, (MaterialChange("arsenic", -5),)))
    assert tracker.inventory == {"arsenic": 0}


def test_a_material_unknown_to_the_catalogue_is_counted_without_a_cap(
    tracker: EngineeringTracker,
) -> None:
    tracker.handle(held(tg_interdictiondata=4))
    tracker.handle(collected("tg_interdictiondata", 400))
    assert tracker.inventory == {"tg_interdictiondata": 404}
    stats = tracker.stats().collection
    assert stats is not None
    assert stats.gained == {None: 400}


def test_names_in_the_game_language_are_remembered(tracker: EngineeringTracker) -> None:
    tracker.handle(InventoryStated(T0, (MaterialChange("arsenic", 1, "Arsenic FR"),)))
    assert tracker.name_of("arsenic") == "Arsenic FR"
    assert tracker.name_of("dataminedwake") is None


# Collection


def test_a_collection_counts_gains_by_category_and_what_was_used(
    tracker: EngineeringTracker,
) -> None:
    first = tracker.handle(collected("arsenic", 3))
    assert first[0] == CollectionStarted(at(1))
    tracker.handle(
        MaterialsChanged(at(2), ChangeCause.REWARDED, (MaterialChange("dataminedwake", 2),))
    )
    # A trade converts: neither gained nor used
    tracker.handle(
        MaterialsChanged(
            at(3),
            ChangeCause.TRADED,
            (MaterialChange("arsenic", -6), MaterialChange("chemicalmanipulators", 1)),
        )
    )
    tracker.handle(rolled())
    stats = tracker.stats().collection
    assert stats is not None
    assert stats.started_at == at(1)
    assert stats.gained == {MaterialCategory.RAW: 3, MaterialCategory.ENCODED: 2}
    assert stats.used == 3


def test_the_collection_ends_when_the_game_closes_or_on_reset(
    tracker: EngineeringTracker,
) -> None:
    assert tracker.handle(GameClosed(at(1))) == []
    tracker.handle(collected("arsenic", 3))
    notifications = tracker.handle(GameClosed(at(9)))
    assert notifications[0] == CollectionEnded(at(9), CollectionEndReason.GAME_CLOSED)
    assert tracker.stats().collection is None
    tracker.handle(collected("arsenic", 3, minutes=20))
    assert tracker.end(at(30), CollectionEndReason.MANUAL)[0] == CollectionEnded(
        at(30), CollectionEndReason.MANUAL
    )


# Goals


def test_a_goal_misses_what_the_inventory_lacks_for_all_its_rolls(
    tracker: EngineeringTracker,
) -> None:
    tracker.add_goal(RANGE)
    [progress] = tracker.stats().goals
    assert progress.needed == {"arsenic": 2, "chemicalmanipulators": 2, "dataminedwake": 2}
    assert progress.missing is None  # inventory unknown
    assert not progress.ready
    tracker.handle(held(arsenic=5, chemicalmanipulators=1))
    [progress] = tracker.stats().goals
    assert progress.missing == {"chemicalmanipulators": 1, "dataminedwake": 2}


def test_a_goal_becomes_ready_once(tracker: EngineeringTracker) -> None:
    tracker.handle(held(arsenic=5, chemicalmanipulators=2, dataminedwake=1))
    tracker.add_goal(RANGE)
    notifications = tracker.handle(collected("dataminedwake", 1))
    assert GoalReady(RANGE) in notifications
    assert updates(notifications)[0].stats.goals_ready == 1
    assert not any(isinstance(n, GoalReady) for n in tracker.handle(collected("arsenic", 1)))


def test_the_shopping_list_adds_up_every_goal(tracker: EngineeringTracker) -> None:
    tracker.handle(held(arsenic=4))
    tracker.add_goal(RANGE)
    tracker.add_goal(MASS_MANAGER)
    assert tracker.shopping_list() == {
        "arsenic": 3,  # 2 + 5 needed, 4 held
        "chemicalmanipulators": 2,
        "dataminedwake": 5,
    }


def test_a_roll_takes_one_off_the_goal_then_the_goal_is_done(
    tracker: EngineeringTracker,
) -> None:
    tracker.add_goal(RANGE)
    first = tracker.handle(rolled())
    after = BlueprintGoal(RANGE.id, "FSD_LongRange", "fsd", grade=5, rolls=1)
    assert GoalProgressed(after) in first
    assert list(tracker.goals) == [after]
    assert GoalDone(after) in tracker.handle(rolled())
    assert list(tracker.goals) == []


@pytest.mark.parametrize(
    "fact",
    [
        rolled(goal_grade=4),
        rolled(item="anaconda_armour_grade3"),  # another module type
        rolled(effect="special_fsd_heavy"),  # an effect, not a roll
    ],
)
def test_other_crafts_leave_the_goal(tracker: EngineeringTracker, fact: BlueprintApplied) -> None:
    tracker.add_goal(RANGE)
    tracker.handle(fact)
    assert tracker.goals == (RANGE,)


def test_an_item_unknown_to_the_catalogue_matches_any_module_type(
    tracker: EngineeringTracker,
) -> None:
    tracker.add_goal(RANGE)
    tracker.handle(rolled(item="int_hyperdrive_size8_class5"))
    [goal] = tracker.goals
    assert isinstance(goal, BlueprintGoal)
    assert goal.rolls == 1


def test_an_effect_application_completes_its_goal(tracker: EngineeringTracker) -> None:
    tracker.add_goal(MASS_MANAGER)
    assert GoalDone(MASS_MANAGER) in tracker.handle(rolled(effect="special_fsd_heavy"))


def test_the_engineers_of_a_goal_are_the_unlocked_ones_offering_it(
    tracker: EngineeringTracker,
) -> None:
    tracker.add_goal(RANGE)
    tracker.add_goal(MASS_MANAGER)
    assert [p.engineers for p in tracker.stats().goals] == [(), ()]
    tracker.handle(
        EngineersStated(T0, (EngineerState(FARSEER, "Felicity Farseer", EngineerStatus.INVITED),))
    )
    assert [p.engineers for p in tracker.stats().goals] == [(), ()]
    tracker.handle(
        EngineerProgressed(
            at(1), EngineerState(FARSEER, "Felicity Farseer", EngineerStatus.UNLOCKED, 1)
        )
    )
    assert [p.engineers for p in tracker.stats().goals] == [(FARSEER,), (FARSEER,)]
    assert tracker.engineers[FARSEER].rank == 1


def test_a_goal_the_catalogue_does_not_know_is_never_ready(tracker: EngineeringTracker) -> None:
    tracker.handle(held())
    tracker.handle(unlocked(FARSEER))
    unknown = BlueprintGoal(GoalId("old"), "FSD_Removed", "fsd", grade=1)
    elsewhere = BlueprintGoal(GoalId("gone"), "FSD_LongRange", "removed_module", grade=5)
    tracker.add_goal(unknown)
    tracker.add_goal(elsewhere)
    first, second = tracker.stats().goals
    assert not first.known
    assert not first.ready
    assert second.known
    assert second.engineers == ()


def test_the_player_changes_goals(tracker: EngineeringTracker) -> None:
    tracker.add_goal(RANGE)
    tracker.load_goals([MASS_MANAGER, RANGE])
    assert tracker.goals == (MASS_MANAGER, RANGE)
    one_roll = BlueprintGoal(RANGE.id, "FSD_LongRange", "fsd", grade=5, rolls=1)
    tracker.replace_goal(one_roll)
    assert tracker.goals == (MASS_MANAGER, one_roll)
    tracker.remove_goal(MASS_MANAGER.id)
    assert list(tracker.goals) == [one_roll]


def test_goals_added_before_the_stored_ones_are_loaded_are_kept(
    tracker: EngineeringTracker,
) -> None:
    tracker.add_goal(RANGE)
    tracker.load_goals([MASS_MANAGER])
    assert tracker.goals == (MASS_MANAGER, RANGE)


def test_a_goal_ready_again_after_a_change_is_reported_again(
    tracker: EngineeringTracker,
) -> None:
    tracker.handle(held(arsenic=10, dataminedwake=10))
    assert GoalReady(MASS_MANAGER) in tracker.add_goal(MASS_MANAGER)
    two = ExperimentalEffectGoal(MASS_MANAGER.id, "special_fsd_heavy", "fsd", applications=2)
    assert GoalReady(two) in tracker.replace_goal(two)
