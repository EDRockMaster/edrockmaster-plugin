from datetime import UTC, datetime

import pytest

from edrockmaster.domain.engineering.goals import (
    MAX_GRADE,
    BlueprintGoal,
    ClassUpgradeGoal,
    ExperimentalEffectGoal,
    GoalId,
)

ID = GoalId("0f8c4b2e")


def test_a_blueprint_goal_takes_one_roll_by_default() -> None:
    goal = BlueprintGoal(ID, "FSD_LongRange", "fsd", grade=5)
    assert goal.rolls == 1


def test_an_experimental_effect_goal_takes_one_application_by_default() -> None:
    goal = ExperimentalEffectGoal(ID, "special_fsd_heavy", "fsd")
    assert goal.applications == 1


@pytest.mark.parametrize("grade", [0, MAX_GRADE + 1])
def test_a_grade_is_from_1_to_5(grade: int) -> None:
    with pytest.raises(ValueError, match="grade"):
        BlueprintGoal(ID, "FSD_LongRange", "fsd", grade=grade)


def test_a_goal_takes_at_least_one_roll() -> None:
    with pytest.raises(ValueError, match="roll"):
        BlueprintGoal(ID, "FSD_LongRange", "fsd", grade=5, rolls=0)


def test_a_goal_takes_at_least_one_application() -> None:
    with pytest.raises(ValueError, match="application"):
        ExperimentalEffectGoal(ID, "special_fsd_heavy", "fsd", applications=0)


@pytest.mark.parametrize("name", ["", " "])
def test_a_goal_names_its_blueprint_and_module(name: str) -> None:
    with pytest.raises(ValueError, match="blueprint"):
        BlueprintGoal(ID, name, "fsd", grade=5)
    with pytest.raises(ValueError, match="module"):
        BlueprintGoal(ID, "FSD_LongRange", name, grade=5)
    with pytest.raises(ValueError, match="effect"):
        ExperimentalEffectGoal(ID, name, "fsd")
    with pytest.raises(ValueError, match="module"):
        ExperimentalEffectGoal(ID, "special_fsd_heavy", name)


def test_a_goal_id_is_not_empty() -> None:
    with pytest.raises(ValueError, match="id"):
        GoalId("")


def test_new_goal_ids_are_unique() -> None:
    assert GoalId.new() != GoalId.new()


SET_AT = datetime(2026, 10, 11, 1, 30, tzinfo=UTC)


def test_a_class_upgrade_goal_raises_an_item_from_one_class_to_another() -> None:
    goal = ClassUpgradeGoal(ID, "tacticalsuit", from_class=1, to_class=3, set_at=SET_AT)
    assert goal.steps == (2, 3)
    # A type of item, until the player names one of theirs
    assert goal.equipment_id is None


@pytest.mark.parametrize(("from_class", "to_class"), [(0, 2), (1, 6), (3, 3), (4, 2)])
def test_a_class_upgrade_goes_up_between_classes_1_and_5(from_class: int, to_class: int) -> None:
    with pytest.raises(ValueError, match="class"):
        ClassUpgradeGoal(ID, "tacticalsuit", from_class, to_class, SET_AT)


def test_a_class_upgrade_goal_names_its_item() -> None:
    with pytest.raises(ValueError, match="item"):
        ClassUpgradeGoal(ID, " ", 1, 2, SET_AT)


def test_a_class_upgrade_goal_knows_when_it_was_set() -> None:
    with pytest.raises(ValueError, match="time zone"):
        ClassUpgradeGoal(ID, "tacticalsuit", 1, 2, datetime(2026, 10, 11))
