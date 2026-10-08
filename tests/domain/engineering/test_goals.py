import pytest

from edrockmaster.domain.engineering.goals import (
    MAX_GRADE,
    BlueprintGoal,
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
