"""Engineering goals stored in a real SQLite file, through the real I/O thread."""

import logging
import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from edrockmaster.application.ports import GoalRepository
from edrockmaster.domain.engineering.goals import (
    BlueprintGoal,
    ClassUpgradeGoal,
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
SET_AT = datetime(2026, 10, 11, 1, 30, 15, tzinfo=UTC)
DOMINATOR = ClassUpgradeGoal(GoalId("d4"), "tacticalsuit", 1, 4, SET_AT, 1878707285049801)
ECLIPSE = ClassUpgradeGoal(GoalId("e5"), "wpn_m_submachinegun_laser_fauto", 2, 5, SET_AT)


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


def test_class_upgrades_are_stored_and_listed_after_the_ship_goals(storage: Storage) -> None:
    for goal in (DOMINATOR, RANGE, ECLIPSE):
        storage.repository.add(goal)
    assert storage.loaded() == (RANGE, DOMINATOR, ECLIPSE)
    started_higher = ClassUpgradeGoal(DOMINATOR.id, "tacticalsuit", 3, 4, SET_AT, 1878707285049801)
    storage.repository.replace(started_higher)
    storage.repository.remove(ECLIPSE.id)
    assert storage.loaded() == (RANGE, started_higher)


def test_the_time_a_goal_was_set_is_kept_in_utc(storage: Storage) -> None:
    paris = timezone(timedelta(hours=2))
    storage.repository.add(
        ClassUpgradeGoal(GoalId("f6"), "utilitysuit", 1, 2, SET_AT.astimezone(paris))
    )
    [goal] = storage.loaded()
    assert isinstance(goal, ClassUpgradeGoal)
    assert goal.set_at == SET_AT
    assert goal.set_at.utcoffset() == timedelta(0)


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
