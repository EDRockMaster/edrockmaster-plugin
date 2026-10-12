"""The engineering goals' calls, on a core context that runs each job at once (ADR 0041)."""

import logging

import pytest

from edrockmaster.desktop.handlers.engineering import EngineeringHandler
from edrockmaster.domain.engineering.goals import BlueprintGoal
from tests.desktop.handlers.fake_core import FakeCore

FSD_GOAL = {"kind": "blueprint", "module": "fsd", "name": "FSD_LongRange", "grade": 5, "count": 2}


@pytest.fixture
def core() -> FakeCore:
    return FakeCore()


@pytest.fixture
def handler(core: FakeCore) -> EngineeringHandler:
    return EngineeringHandler(core.context)


def rolls(core: FakeCore) -> list[int]:
    return [g.rolls for g in core.companion.engineering.goals if isinstance(g, BlueprintGoal)]


def ids(core: FakeCore) -> list[str]:
    return [goal.id.value for goal in core.companion.engineering.goals]


def test_goals_added_changed_and_removed(core: FakeCore, handler: EngineeringHandler) -> None:
    handler.add_goal(FSD_GOAL)
    [goal] = core.companion.engineering.goals
    assert isinstance(goal, BlueprintGoal)
    assert (goal.grade, goal.rolls) == (5, 2)
    assert core.applied  # the view follows
    handler.change_goal(goal.id.value, 3)
    assert rolls(core) == [3]
    handler.remove_goal(goal.id.value)
    assert core.companion.engineering.goals == ()


def test_the_player_s_priority(core: FakeCore, handler: EngineeringHandler) -> None:
    handler.add_goal(FSD_GOAL)
    handler.add_goal({"kind": "effect", "module": "fsd", "name": "special_fsd_heavy"})
    first, second = ids(core)
    handler.order_goals([second, "nowhere"])
    assert ids(core) == [second, first]


def test_requests_that_cannot_be_done_are_logged(
    core: FakeCore, handler: EngineeringHandler, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        handler.add_goal({**FSD_GOAL, "grade": 9})
        handler.change_goal("nowhere", 2)
        handler.remove_goal("nowhere")
        handler.order_goals("nowhere")  # type: ignore[arg-type]
        handler.add_goal(FSD_GOAL)
        handler.change_goal(ids(core)[0], 0)
    assert "Goal refused" in caplog.text
    assert "No goal 'nowhere' to change" in caplog.text
    assert "No goal 'nowhere' to remove" in caplog.text
    assert "Goal order refused" in caplog.text
    assert "Goal change refused" in caplog.text
    assert rolls(core) == [2]


def test_the_goal_form_s_catalogue_follows_the_language(
    core: FakeCore, handler: EngineeringHandler
) -> None:
    english = handler.catalogue()
    assert english["modules"][0]["name"].startswith("en:")
    assert handler.catalogue() is english  # built once per language
    core.language = "fr"
    assert handler.catalogue()["modules"][0]["name"].startswith("fr:")
