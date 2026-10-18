"""Engineering goals in the local database (ADR 0017, ADR 0018, ADR 0027).

``SqliteGoalRepository`` implements the application's ``GoalRepository``: each
call becomes a job of the I/O thread, and the goals read are handed back to the
core thread. The functions below are the SQL, run on the I/O thread only.

Each kind of goal has its table; their order, the player's priority (ADR 0033),
is ``goal_priority``: one rank per goal, whatever its kind, a new goal last.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import assert_never

from edrockmaster.domain.engineering.goals import (
    BlueprintGoal,
    ClassUpgradeGoal,
    EngineerUnlockGoal,
    ExperimentalEffectGoal,
    Goal,
    GoalId,
    ModificationGoal,
)
from edrockmaster.infrastructure.database import LocalDatabase, transaction
from edrockmaster.infrastructure.worker import Job

type Dispatch = Callable[[Callable[[], None]], None]
"""Runs a callback on the core thread, later; callable from any thread."""

_BLUEPRINT = "blueprint"
_EXPERIMENTAL_EFFECT = "experimental_effect"

type _Row = tuple[str, str, str, str, int | None, int]
type _ClassRow = tuple[str, str, int, int, str, int | None]
type _ModificationRow = tuple[str, str, str, str, int | None]


def _row(goal: BlueprintGoal | ExperimentalEffectGoal) -> _Row:
    match goal:
        case BlueprintGoal():
            return (goal.id.value, _BLUEPRINT, goal.blueprint, goal.module, goal.grade, goal.rolls)
        case ExperimentalEffectGoal():
            return (
                goal.id.value,
                _EXPERIMENTAL_EFFECT,
                goal.effect,
                goal.module,
                None,
                goal.applications,
            )
        case _:  # pragma: no cover - exhaustiveness checked by mypy
            assert_never(goal)


def _goal(row: _Row) -> Goal:
    goal_id, kind, name, module, grade, count = row
    if kind == _BLUEPRINT and grade is not None:
        return BlueprintGoal(GoalId(goal_id), name, module, grade, count)
    if kind == _EXPERIMENTAL_EFFECT:
        return ExperimentalEffectGoal(GoalId(goal_id), name, module, count)
    raise ValueError(f"unknown kind of goal {kind!r}")  # the table's checks forbid it


def _class_row(goal: ClassUpgradeGoal) -> _ClassRow:
    return (
        goal.id.value,
        goal.item,
        goal.from_class,
        goal.to_class,
        goal.set_at.astimezone(UTC).isoformat(),
        goal.equipment_id,
    )


def _class_goal(row: _ClassRow) -> ClassUpgradeGoal:
    goal_id, item, from_class, to_class, set_at, equipment_id = row
    return ClassUpgradeGoal(
        GoalId(goal_id), item, from_class, to_class, datetime.fromisoformat(set_at), equipment_id
    )


def _modification_row(goal: ModificationGoal) -> _ModificationRow:
    return (
        goal.id.value,
        goal.item,
        goal.modification,
        goal.set_at.astimezone(UTC).isoformat(),
        goal.equipment_id,
    )


def _modification_goal(row: _ModificationRow) -> ModificationGoal:
    goal_id, item, modification, set_at, equipment_id = row
    return ModificationGoal(
        GoalId(goal_id), item, modification, datetime.fromisoformat(set_at), equipment_id
    )


def read_goals(connection: sqlite3.Connection) -> tuple[Goal, ...]:
    """Every goal, in the player's priority."""
    ranked = [
        goal_id
        for (goal_id,) in connection.execute("SELECT goal_id FROM goal_priority ORDER BY rank")
    ]
    goals = {goal.id.value: goal for goal in _read_each_kind(connection)}
    # A goal without a rank cannot be stored: it would come last
    return (
        *(goals.pop(goal_id) for goal_id in ranked if goal_id in goals),
        *goals.values(),
    )


def _read_each_kind(connection: sqlite3.Connection) -> tuple[Goal, ...]:
    rows = connection.execute(
        "SELECT id, kind, name, module, grade, count FROM engineering_goal ORDER BY position"
    )
    class_rows = connection.execute(
        "SELECT id, item, from_class, to_class, set_at, equipment_id FROM class_upgrade_goal "
        "ORDER BY position"
    )
    modification_rows = connection.execute(
        "SELECT id, item, modification, set_at, equipment_id FROM modification_goal "
        "ORDER BY position"
    )
    unlock_rows = connection.execute(
        "SELECT id, engineer_id FROM engineer_unlock_goal ORDER BY position"
    )
    return (
        *(_goal(row) for row in rows),
        *(_class_goal(row) for row in class_rows),
        *(_modification_goal(row) for row in modification_rows),
        *(EngineerUnlockGoal(GoalId(goal_id), engineer_id) for goal_id, engineer_id in unlock_rows),
    )


def insert_goal(connection: sqlite3.Connection, goal: Goal) -> None:
    """The goal, last in the priority."""
    with transaction(connection):
        _insert(connection, goal)
        connection.execute(
            "INSERT INTO goal_priority (goal_id, rank) "
            "SELECT ?, coalesce(max(rank), 0) + 1 FROM goal_priority",
            (goal.id.value,),
        )


def _insert(connection: sqlite3.Connection, goal: Goal) -> None:
    if isinstance(goal, ClassUpgradeGoal):
        connection.execute(
            "INSERT INTO class_upgrade_goal "
            "(id, item, from_class, to_class, set_at, equipment_id, position) "
            "SELECT ?, ?, ?, ?, ?, ?, coalesce(max(position), 0) + 1 FROM class_upgrade_goal",
            _class_row(goal),
        )
        return
    if isinstance(goal, EngineerUnlockGoal):
        connection.execute(
            "INSERT INTO engineer_unlock_goal (id, engineer_id, position) "
            "SELECT ?, ?, coalesce(max(position), 0) + 1 FROM engineer_unlock_goal",
            (goal.id.value, goal.engineer_id),
        )
        return
    if isinstance(goal, ModificationGoal):
        connection.execute(
            "INSERT INTO modification_goal "
            "(id, item, modification, set_at, equipment_id, position) "
            "SELECT ?, ?, ?, ?, ?, coalesce(max(position), 0) + 1 FROM modification_goal",
            _modification_row(goal),
        )
        return
    connection.execute(
        "INSERT INTO engineering_goal (id, kind, name, module, grade, count, position) "
        "SELECT ?, ?, ?, ?, ?, ?, coalesce(max(position), 0) + 1 FROM engineering_goal",
        _row(goal),
    )


def update_goal(connection: sqlite3.Connection, goal: Goal) -> None:
    if isinstance(goal, ClassUpgradeGoal):
        goal_id, item, from_class, to_class, set_at, equipment_id = _class_row(goal)
        connection.execute(
            "UPDATE class_upgrade_goal SET item = ?, from_class = ?, to_class = ?, set_at = ?, "
            "equipment_id = ? WHERE id = ?",
            (item, from_class, to_class, set_at, equipment_id, goal_id),
        )
        return
    if isinstance(goal, EngineerUnlockGoal):
        connection.execute(
            "UPDATE engineer_unlock_goal SET engineer_id = ? WHERE id = ?",
            (goal.engineer_id, goal.id.value),
        )
        return
    if isinstance(goal, ModificationGoal):
        goal_id, item, modification, set_at, equipment_id = _modification_row(goal)
        connection.execute(
            "UPDATE modification_goal SET item = ?, modification = ?, set_at = ?, "
            "equipment_id = ? WHERE id = ?",
            (item, modification, set_at, equipment_id, goal_id),
        )
        return
    goal_id, kind, name, module, grade, count = _row(goal)
    connection.execute(
        "UPDATE engineering_goal SET kind = ?, name = ?, module = ?, grade = ?, count = ? "
        "WHERE id = ?",
        (kind, name, module, grade, count, goal_id),
    )


def delete_goal(connection: sqlite3.Connection, goal_id: GoalId) -> None:
    with transaction(connection):
        connection.execute("DELETE FROM engineering_goal WHERE id = ?", (goal_id.value,))
        connection.execute("DELETE FROM class_upgrade_goal WHERE id = ?", (goal_id.value,))
        connection.execute("DELETE FROM modification_goal WHERE id = ?", (goal_id.value,))
        connection.execute("DELETE FROM engineer_unlock_goal WHERE id = ?", (goal_id.value,))
        connection.execute("DELETE FROM goal_priority WHERE goal_id = ?", (goal_id.value,))


def reorder_goals(connection: sqlite3.Connection, order: Sequence[GoalId]) -> None:
    """The goals the order names first, in its order, then the others as they were."""
    with transaction(connection):
        ranked = [
            goal_id
            for (goal_id,) in connection.execute("SELECT goal_id FROM goal_priority ORDER BY rank")
        ]
        named = [goal_id.value for goal_id in dict.fromkeys(order) if goal_id.value in ranked]
        ordered = named + [goal_id for goal_id in ranked if goal_id not in named]
        connection.execute("DELETE FROM goal_priority")
        connection.executemany(
            "INSERT INTO goal_priority (goal_id, rank) VALUES (?, ?)",
            [(goal_id, rank) for rank, goal_id in enumerate(ordered, start=1)],
        )


class SqliteGoalRepository:
    def __init__(
        self,
        database: LocalDatabase,
        submit: Callable[[Job], None],
        dispatch: Dispatch,
        logger: logging.Logger,
    ) -> None:
        self._database = database
        self._submit = submit
        self._dispatch = dispatch
        self._logger = logger

    def load(self, on_loaded: Callable[[tuple[Goal, ...]], None]) -> None:
        def job() -> None:
            goals: tuple[Goal, ...] = ()
            if self._database.is_open:
                goals = read_goals(self._database.connection())
            else:
                self._logger.warning("Engineering goals not read: no local database")
            self._dispatch(lambda: on_loaded(goals))

        self._submit(job)

    def add(self, goal: Goal) -> None:
        self._write("added", lambda connection: insert_goal(connection, goal))

    def replace(self, goal: Goal) -> None:
        self._write("changed", lambda connection: update_goal(connection, goal))

    def remove(self, goal_id: GoalId) -> None:
        self._write("removed", lambda connection: delete_goal(connection, goal_id))

    def reorder(self, order: Sequence[GoalId]) -> None:
        self._write("priority", lambda connection: reorder_goals(connection, order))

    def _write(self, what: str, write: Callable[[sqlite3.Connection], None]) -> None:
        def job() -> None:
            if self._database.is_open:
                write(self._database.connection())
            else:
                self._logger.warning("Engineering goal %s, not stored: no local database", what)

        self._submit(job)
