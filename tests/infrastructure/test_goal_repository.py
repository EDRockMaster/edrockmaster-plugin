"""Engineering goals stored in a real SQLite file, through the real I/O thread."""

import logging
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from edrockmaster.application.ports import GoalRepository
from edrockmaster.domain.engineering.goals import (
    BlueprintGoal,
    ExperimentalEffectGoal,
    Goal,
    GoalId,
)
from edrockmaster.infrastructure.database import FILE_NAME, LocalDatabase
from edrockmaster.infrastructure.goal_repository import SqliteGoalRepository
from edrockmaster.infrastructure.worker import THREAD_NAME, IoWorker

logger = logging.getLogger("test.goals")

RANGE = BlueprintGoal(GoalId("a1"), "FSD_LongRange", "fsd", grade=5, rolls=3)
MASS_MANAGER = ExperimentalEffectGoal(GoalId("b2"), "special_fsd_heavy", "fsd")
DIRTY = BlueprintGoal(GoalId("c3"), "Engine_Dirty", "thrusters", grade=4)


class Storage:
    """A repository on the I/O thread; callbacks for the main thread are run by ``loaded()``."""

    def __init__(self, directory: Path) -> None:
        self.database = LocalDatabase(directory / FILE_NAME, logger)
        self.worker = IoWorker(logger)
        self.worker.start()
        self.dispatched: list[Callable[[], None]] = []
        self.repository: GoalRepository = SqliteGoalRepository(
            self.database, self.worker.submit, self.dispatched.append, logger
        )

    def open(self) -> None:
        def job() -> None:
            assert self.database.open().available

        self.worker.submit(job)

    def loaded(self) -> tuple[Goal, ...]:
        received: list[tuple[Goal, ...]] = []
        threads: list[str] = []

        def on_loaded(goals: tuple[Goal, ...]) -> None:
            received.append(goals)
            threads.append(threading.current_thread().name)

        self.repository.load(on_loaded)
        self.flush()
        assert not received, "results reach the main thread through the dispatcher only"
        for callback in self.dispatched:
            callback()
        self.dispatched.clear()
        assert threads == [threading.current_thread().name]
        [goals] = received
        return goals

    def flush(self) -> None:
        done = threading.Event()
        self.worker.submit(done.set)
        assert done.wait(timeout=2)

    def stop(self) -> None:
        self.worker.submit(self.database.close)
        self.worker.stop()


@pytest.fixture
def storage(tmp_path: Path) -> Iterator[Storage]:
    storage = Storage(tmp_path)
    storage.open()
    yield storage
    storage.stop()


def test_goals_are_listed_in_the_order_they_were_added(storage: Storage) -> None:
    for goal in (RANGE, MASS_MANAGER, DIRTY):
        storage.repository.add(goal)
    assert storage.loaded() == (RANGE, MASS_MANAGER, DIRTY)


def test_a_changed_goal_keeps_its_place(storage: Storage) -> None:
    storage.repository.add(RANGE)
    storage.repository.add(DIRTY)
    fewer_rolls = BlueprintGoal(RANGE.id, "FSD_LongRange", "fsd", grade=5, rolls=1)
    storage.repository.replace(fewer_rolls)
    assert storage.loaded() == (fewer_rolls, DIRTY)


def test_a_removed_goal_is_gone_and_new_ones_come_last(storage: Storage) -> None:
    for goal in (RANGE, MASS_MANAGER):
        storage.repository.add(goal)
    storage.repository.remove(RANGE.id)
    storage.repository.add(DIRTY)
    storage.repository.add(RANGE)
    assert storage.loaded() == (MASS_MANAGER, DIRTY, RANGE)


def test_goals_survive_a_restart(tmp_path: Path) -> None:
    first = Storage(tmp_path)
    first.open()
    first.repository.add(MASS_MANAGER)
    first.stop()
    second = Storage(tmp_path)
    second.open()
    try:
        assert second.loaded() == (MASS_MANAGER,)
    finally:
        second.stop()


def test_storage_runs_on_the_io_thread_only(storage: Storage) -> None:
    storage.flush()
    assert storage.database.owner == THREAD_NAME


def test_without_a_database_nothing_is_stored_and_no_goal_is_read(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    storage = Storage(tmp_path)  # never opened
    try:
        with caplog.at_level(logging.WARNING):
            storage.repository.add(RANGE)
            assert storage.loaded() == ()
    finally:
        storage.stop()
    assert "not stored" in caplog.text
    assert "not read" in caplog.text
