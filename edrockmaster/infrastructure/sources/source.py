"""Asking a community source, with the local cache (ADR 0039).

``CommunitySource.ask`` runs on the I/O thread, which owns the local database:
a fresh cached answer is used as it is; otherwise the source is asked, and its
answer kept. When the source fails, the cached answer, however old, is used
and says why; with nothing cached, the answer is the failure. The callback is
handed to the core thread.

The answer is kept as the source gave it, and read again each time: a parser
that changes reads the old answers too.

A source may take a request as a job and answer later (ADR 0057): ``follow``
asks as ``ask`` does, but an answer the parser reads as ``Pending`` is handed on
and not kept; the job's result, once read, is kept under the same request.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from edrockmaster.application.community import (
    Answer,
    Failed,
    Found,
    Pending,
    Source,
    Unavailable,
)
from edrockmaster.infrastructure.database import LocalDatabase
from edrockmaster.infrastructure.sources.http import SourceError
from edrockmaster.infrastructure.worker import Job

type Dispatch = Callable[[Callable[[], None]], None]


def read_cached(
    connection: sqlite3.Connection, source: Source, request: str
) -> tuple[Any, datetime] | None:
    row = connection.execute(
        "SELECT answer, read_at FROM source_cache WHERE source = ? AND request = ?",
        (source.value, request),
    ).fetchone()
    if row is None:
        return None
    answer, read_at = row
    return json.loads(answer), datetime.fromisoformat(read_at)


def store_cached(
    connection: sqlite3.Connection, source: Source, request: str, answer: Any, read_at: datetime
) -> None:
    connection.execute(
        "INSERT INTO source_cache (source, request, read_at, answer) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (source, request) DO UPDATE SET read_at = excluded.read_at, "
        "answer = excluded.answer",
        (source.value, request, read_at.isoformat(), json.dumps(answer)),
    )


def clear_cached(connection: sqlite3.Connection, source: Source) -> None:
    connection.execute("DELETE FROM source_cache WHERE source = ?", (source.value,))


class CommunitySource:
    def __init__(  # noqa: PLR0913 - the source, its switch and the threads it runs on
        self,
        source: Source,
        database: LocalDatabase,
        *,
        enabled: Callable[[], bool],
        submit: Callable[[Job], None],
        dispatch: Dispatch,
        now: Callable[[], datetime],
        logger: logging.Logger,
    ) -> None:
        self.source = source
        self._database = database
        self._enabled = enabled
        self._submit = submit
        self._dispatch = dispatch
        self._now = now
        self._logger = logger

    def ask[T](  # noqa: PLR0913 - what to ask, how to read it, and where to answer
        self,
        request: str,
        fetch: Callable[[], Any],
        parse: Callable[[Any], T],
        max_age: timedelta,
        on_answer: Callable[[Answer[T]], None],
        *,
        refresh: bool = False,
    ) -> None:
        """``request`` identifies the answer in the cache; ``fetch`` asks the source."""

        def job() -> None:
            answer = self._answer(request, fetch, parse, max_age, refresh=refresh)
            assert not isinstance(answer, Pending), "only a job's parser gives Pending"
            self._dispatch(lambda: on_answer(answer))

        self._submit(job)

    def follow[T](  # noqa: PLR0913 - as ``ask``
        self,
        request: str,
        fetch: Callable[[], Any],
        parse: Callable[[Any], T | Pending],
        max_age: timedelta,
        on_answer: Callable[[Answer[T] | Pending], None],
        *,
        refresh: bool = False,
    ) -> None:
        """As ``ask``, for a source that answers with a job: ``Pending`` until its result."""

        def job() -> None:
            answer = self._answer(request, fetch, parse, max_age, refresh=refresh)
            self._dispatch(lambda: on_answer(answer))

        self._submit(job)

    def clear(self) -> None:
        """Forget every answer of the source (the player turned it off, or asked)."""

        def job() -> None:
            if self._database.is_open:
                clear_cached(self._database.connection(), self.source)

        self._submit(job)

    def _answer[T](  # noqa: PLR0911 - a return for each way the source answers
        self,
        request: str,
        fetch: Callable[[], Any],
        parse: Callable[[Any], T | Pending],
        max_age: timedelta,
        *,
        refresh: bool,
    ) -> Answer[T] | Pending:
        if not self._enabled():
            return Failed(self.source, Unavailable.OFF)
        connection = self._database.connection() if self._database.is_open else None
        cached = read_cached(connection, self.source, request) if connection else None
        now = self._now()
        if cached is not None and not refresh and now - cached[1] <= max_age:
            return self._read(parse, *cached)
        try:
            answer = fetch()
            value = parse(answer)
        except SourceError as error:
            self._logger.info("%s gave nothing (%s): %s", self.source.value, error.reason, error)
            if cached is None:
                return Failed(self.source, error.reason)
            return self._read(parse, *cached, unavailable=error.reason)
        except (KeyError, TypeError, ValueError) as error:
            self._logger.warning("%s answered in an unknown format: %r", self.source.value, error)
            return Failed(self.source, Unavailable.DOWN)
        if isinstance(value, Pending):
            return value  # nothing to keep yet
        if connection is not None:
            store_cached(connection, self.source, request, answer, now)
        return Found(value, self.source, now)

    def _read[T](
        self,
        parse: Callable[[Any], T | Pending],
        answer: Any,
        read_at: datetime,
        unavailable: Unavailable | None = None,
    ) -> Answer[T] | Pending:
        """A kept answer: never ``Pending``, which is not kept."""
        try:
            value = parse(answer)
            return (
                value
                if isinstance(value, Pending)
                else Found(value, self.source, read_at, unavailable)
            )
        except (KeyError, TypeError, ValueError) as error:
            self._logger.warning("Cached answer of %s unreadable: %r", self.source.value, error)
            return Failed(self.source, unavailable or Unavailable.DOWN)
