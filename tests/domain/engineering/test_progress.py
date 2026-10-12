"""How far one goal is, from the catalogue and what is held, on its own."""

from datetime import UTC, datetime

from edrockmaster.domain.engineering.goals import (
    BlueprintGoal,
    ExperimentalEffectGoal,
    GoalId,
    ModificationGoal,
)
from edrockmaster.domain.engineering.journal import EngineerState, EngineerStatus
from edrockmaster.domain.engineering.progress import Holdings, missing, needed, progress
from tests.domain.engineering.catalogue_data import catalogue

T0 = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
# Two rolls of arsenic 1, chemical manipulators 1, datamined wake 1
RANGE = BlueprintGoal(GoalId("range"), "FSD_LongRange", "fsd", grade=5, rolls=2)
MASS_MANAGER = ExperimentalEffectGoal(GoalId("mass"), "special_fsd_heavy", "fsd")
BACKPACK = ModificationGoal(GoalId("backpack"), "tacticalsuit", "suit_backpackcapacity", T0)
NOTHING = Holdings(None, None, {})


def test_missing_is_what_is_held_short_of_what_is_needed() -> None:
    assert missing({"b": 3, "a": 2}, {"a": 5, "b": 1}) == {"b": 2}
    assert missing({"a": 2}, {}) == {"a": 2}


def test_a_blueprint_takes_its_grade_s_ingredients_times_its_rolls() -> None:
    assert needed(RANGE, catalogue()) == {
        "arsenic": 2,
        "chemicalmanipulators": 2,
        "dataminedwake": 2,
    }
    unknown = BlueprintGoal(GoalId("x"), "Nothing_Known", "fsd", grade=5)
    assert needed(unknown, catalogue()) is None
    assert not progress(unknown, catalogue(), NOTHING).known


def test_nothing_is_missing_or_ready_while_the_inventory_is_unknown() -> None:
    assert progress(RANGE, catalogue(), NOTHING).missing is None
    assert not progress(RANGE, catalogue(), NOTHING).ready
    held = Holdings({"arsenic": 2, "chemicalmanipulators": 2, "dataminedwake": 2}, None, {})
    assert progress(RANGE, catalogue(), held).ready


def test_only_unlocked_engineers_offer_a_goal() -> None:
    # Felicity Farseer (300100) engineers frame shift drives
    invited = {300100: EngineerState(300100, "Felicity Farseer", EngineerStatus.INVITED)}
    assert progress(RANGE, catalogue(), Holdings(None, None, invited)).engineers == ()
    unlocked = {300100: EngineerState(300100, "Felicity Farseer", EngineerStatus.UNLOCKED, 5)}
    holdings = Holdings(None, None, unlocked)
    assert progress(RANGE, catalogue(), holdings).engineers == (300100,)
    # Whoever engineers the module type applies its experimental effects
    assert progress(MASS_MANAGER, catalogue(), holdings).engineers == (300100,)


def test_an_on_foot_goal_counts_the_on_foot_materials_only() -> None:
    ship_only = Holdings({"graphene": 10, "internalcorrespondence": 10}, None, {})
    assert progress(BACKPACK, catalogue(), ship_only).missing is None
    on_foot = Holdings(None, {"graphene": 3, "internalcorrespondence": 5}, {})
    found = progress(BACKPACK, catalogue(), on_foot)
    assert found.missing == {}
    assert found.credits >= 0
