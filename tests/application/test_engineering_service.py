from collections.abc import Sequence
from datetime import timedelta

import pytest

from edrockmaster.application.engineering_service import EngineeringService
from edrockmaster.domain.engineering.goals import BlueprintGoal, GoalId
from edrockmaster.domain.engineering.session import (
    CollectionEnded,
    CollectionEndReason,
    CollectionStarted,
    EngineeringNotification,
    EngineeringUpdated,
)
from edrockmaster.domain.journal_reading import Entry
from tests.domain.engineering.catalogue_data import catalogue
from tests.fakes import FakeGoalRepository, FixedClock
from tests.journal_entries import T0, timestamp

RANGE = BlueprintGoal(GoalId("range"), "FSD_LongRange", "fsd", grade=5, rolls=2)


def craft(minutes: int) -> Entry:
    return {
        "timestamp": timestamp(minutes),
        "event": "EngineerCraft",
        "Module": "int_hyperdrive_size5_class5",
        "Ingredients": [{"Name": "arsenic", "Count": 1}],
        "EngineerID": 300100,
        "BlueprintName": "FSD_LongRange",
        "Level": 5,
    }


@pytest.fixture
def repository() -> FakeGoalRepository:
    return FakeGoalRepository([RANGE])


@pytest.fixture
def service(repository: FakeGoalRepository) -> EngineeringService:
    return EngineeringService(catalogue(), repository, FixedClock(T0 + timedelta(hours=1)))


def loaded(service: EngineeringService) -> list[Sequence[EngineeringNotification]]:
    published: list[Sequence[EngineeringNotification]] = []
    service.load_goals(published.append)
    return published


def test_the_stored_goals_are_loaded(service: EngineeringService) -> None:
    [notifications] = loaded(service)
    assert isinstance(notifications[-1], EngineeringUpdated)
    assert service.goals == (RANGE,)


def test_a_roll_in_the_journal_is_stored(
    service: EngineeringService, repository: FakeGoalRepository
) -> None:
    loaded(service)
    notifications = service.handle_journal_entry(craft(0))
    assert isinstance(notifications[0], CollectionStarted)
    [stored] = repository.stored
    assert isinstance(stored, BlueprintGoal)
    assert stored.rolls == 1
    service.handle_journal_entry(craft(1))
    assert repository.stored == []
    assert service.goals == ()


def test_the_player_changes_are_stored(
    service: EngineeringService, repository: FakeGoalRepository
) -> None:
    other = BlueprintGoal(GoalId.new(), "FSD_LongRange", "fsd", grade=5)
    service.add_goal(other)
    assert repository.stored == [RANGE, other]
    one = BlueprintGoal(RANGE.id, "FSD_LongRange", "fsd", grade=5, rolls=1)
    service.replace_goal(one)
    service.remove_goal(other.id)
    assert repository.stored == [one]


def test_reset_ends_the_collection(service: EngineeringService) -> None:
    assert service.reset_session() == []
    service.handle_journal_entry(
        {"timestamp": timestamp(0), "event": "MaterialCollected", "Name": "arsenic", "Count": 3}
    )
    assert service.reset_session()[0] == CollectionEnded(
        T0 + timedelta(hours=1), CollectionEndReason.MANUAL
    )


def test_queries(service: EngineeringService) -> None:
    loaded(service)
    service.handle_journal_entry(
        {
            "timestamp": timestamp(0),
            "event": "Materials",
            "Raw": [{"Name": "arsenic", "Name_Localised": "Arsenic", "Count": 1}],
        }
    )
    assert service.inventory == {"arsenic": 1}
    assert service.name_of("arsenic") == "Arsenic"
    assert service.shopping_list() == {"arsenic": 1, "chemicalmanipulators": 2, "dataminedwake": 2}
    assert service.engineers == {}
    assert service.catalogue.materials["arsenic"].grade == 2
    assert service.stats.inventory_known
    assert service.handle_journal_entry({"timestamp": timestamp(1), "event": "Music"}) == []
