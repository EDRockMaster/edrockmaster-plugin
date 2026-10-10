"""Engineering goals in the local database (ADR 0017, ADR 0018).

``SqliteGoalRepository`` implements the application's ``GoalRepository``: each
call becomes a job of the I/O thread, and the goals read are handed back to the
core thread. The functions below are the SQL, run on the I/O thread only.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from typing import assert_never

from edrockmaster.domain.engineering.goals import (
    BlueprintGoal,
    ExperimentalEffectGoal,
    Goal,
    GoalId,
)
from edrockmaster.infrastructure.database import LocalDatabase
from edrockmaster.infrastructure.worker import Job

type Dispatch = Callable[[Callable[[], None]], None]
"""Runs a callback on the core thread, later; callable from any thread."""

_BLUEPRINT = "blueprint"
_EXPERIMENTAL_EFFECT = "experimental_effect"

type _Row = tuple[str, str, str, str, int | None, int]


def _row(goal: Goal) -> _Row:
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


def read_goals(connection: sqlite3.Connection) -> tuple[Goal, ...]:
    rows = connection.execute(
        "SELECT id, kind, name, module, grade, count FROM engineering_goal ORDER BY position"
    )
    return tuple(_goal(row) for row in rows)


def insert_goal(connection: sqlite3.Connection, goal: Goal) -> None:
    connection.execute(
        "INSERT INTO engineering_goal (id, kind, name, module, grade, count, position) "
        "SELECT ?, ?, ?, ?, ?, ?, coalesce(max(position), 0) + 1 FROM engineering_goal",
        _row(goal),
    )


def update_goal(connection: sqlite3.Connection, goal: Goal) -> None:
    goal_id, kind, name, module, grade, count = _row(goal)
    connection.execute(
        "UPDATE engineering_goal SET kind = ?, name = ?, module = ?, grade = ?, count = ? "
        "WHERE id = ?",
        (kind, name, module, grade, count, goal_id),
    )


def delete_goal(connection: sqlite3.Connection, goal_id: GoalId) -> None:
    connection.execute("DELETE FROM engineering_goal WHERE id = ?", (goal_id.value,))


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

    def _write(self, what: str, write: Callable[[sqlite3.Connection], None]) -> None:
        def job() -> None:
            if self._database.is_open:
                write(self._database.connection())
            else:
                self._logger.warning("Engineering goal %s, not stored: no local database", what)

        self._submit(job)
