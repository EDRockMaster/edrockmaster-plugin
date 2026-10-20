"""Asking a source through the local cache (ADR 0039), on a real SQLite file."""

import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from edrockmaster.application.community import (
    Answer,
    Failed,
    Found,
    Pending,
    Source,
    Unavailable,
)
from edrockmaster.infrastructure.database import FILE_NAME, LocalDatabase
from edrockmaster.infrastructure.sources.http import SourceError
from edrockmaster.infrastructure.sources.source import CommunitySource, read_cached

NOW = datetime(2026, 10, 11, 21, 0, tzinfo=UTC)
logger = logging.getLogger("test.sources")


class Setup:
    def __init__(self, database: LocalDatabase) -> None:
        self.database = database
        self.enabled = True
        self.now = NOW
        self.answers: list[Answer[int]] = []
        self.asked = 0
        self.source = CommunitySource(
            Source.ARDENT,
            database,
            enabled=lambda: self.enabled,
            submit=lambda job: job(),
            dispatch=lambda callback: callback(),
            now=lambda: self.now,
            logger=logger,
        )

    def ask(self, fetch: Callable[[], Any], *, refresh: bool = False) -> Answer[int]:
        def counted() -> Any:
            self.asked += 1
            return fetch()

        self.source.ask(
            "request", counted, lambda answer: int(answer["value"]), timedelta(hours=1),
            self.answers.append, refresh=refresh,
        )  # fmt: skip
        return self.answers[-1]


@pytest.fixture
def setup(tmp_path: Path) -> Iterator[Setup]:
    database = LocalDatabase(tmp_path / FILE_NAME, logger)
    database.open()
    yield Setup(database)
    database.close()


def down() -> Any:
    raise SourceError(Unavailable.DOWN, "no network")


def test_an_answer_is_kept_and_used_while_fresh(setup: Setup) -> None:
    assert setup.ask(lambda: {"value": 1}) == Found(1, Source.ARDENT, NOW)
    setup.now += timedelta(minutes=59)
    assert setup.ask(lambda: {"value": 2}) == Found(1, Source.ARDENT, NOW)
    assert setup.asked == 1


def test_an_old_answer_is_asked_again(setup: Setup) -> None:
    setup.ask(lambda: {"value": 1})
    setup.now += timedelta(hours=2)
    assert setup.ask(lambda: {"value": 2}) == Found(2, Source.ARDENT, setup.now)
    assert read_cached(setup.database.connection(), Source.ARDENT, "request") == (
        {"value": 2},
        setup.now,
    )


def test_refresh_asks_the_source_even_with_a_fresh_answer(setup: Setup) -> None:
    setup.ask(lambda: {"value": 1})
    assert setup.ask(lambda: {"value": 2}, refresh=True).value == 2  # type: ignore[union-attr]


def test_a_failing_source_gives_the_cached_answer_and_says_why(setup: Setup) -> None:
    setup.ask(lambda: {"value": 1})
    setup.now += timedelta(days=3)
    assert setup.ask(down) == Found(1, Source.ARDENT, NOW, Unavailable.DOWN)


def test_a_failing_source_with_nothing_cached_is_the_failure(setup: Setup) -> None:
    assert setup.ask(down) == Failed(Source.ARDENT, Unavailable.DOWN)


def test_a_source_turned_off_is_not_asked(setup: Setup) -> None:
    setup.enabled = False
    assert setup.ask(lambda: {"value": 1}) == Failed(Source.ARDENT, Unavailable.OFF)
    assert setup.asked == 0


def test_an_answer_in_an_unknown_format_is_not_kept(
    setup: Setup, caplog: pytest.LogCaptureFixture
) -> None:
    assert setup.ask(lambda: {"other": 1}) == Failed(Source.ARDENT, Unavailable.DOWN)
    assert "unknown format" in caplog.text
    assert read_cached(setup.database.connection(), Source.ARDENT, "request") is None


def test_a_cached_answer_that_can_no_longer_be_read_is_down(setup: Setup) -> None:
    setup.ask(lambda: {"value": 1})
    setup.database.connection().execute("UPDATE source_cache SET answer = '{}'")
    assert setup.ask(down) == Failed(Source.ARDENT, Unavailable.DOWN)


def test_clearing_forgets_the_source_s_answers(setup: Setup) -> None:
    setup.ask(lambda: {"value": 1})
    setup.source.clear()
    assert read_cached(setup.database.connection(), Source.ARDENT, "request") is None


def test_without_a_database_the_source_is_asked_each_time(tmp_path: Path) -> None:
    setup = Setup(LocalDatabase(tmp_path / FILE_NAME, logger))
    assert setup.ask(lambda: {"value": 1}) == Found(1, Source.ARDENT, NOW)
    assert setup.ask(lambda: {"value": 2}) == Found(2, Source.ARDENT, NOW)
    setup.source.clear()  # nothing to clear


def job_answer(answer: Any) -> int | Pending:
    if answer["status"] == "queued":
        return Pending(Source.SPANSH, str(answer["job"]))
    return int(answer["value"])


def follow(setup: Setup, fetch: Callable[[], Any], *, refresh: bool = False) -> object:
    answers: list[Answer[int] | Pending] = []
    setup.source.follow(
        "route", fetch, job_answer, timedelta(minutes=15), answers.append, refresh=refresh
    )
    return answers[-1]


def test_a_job_still_running_is_pending_and_not_kept(setup: Setup) -> None:
    # Spansh computes a route as a job (ADR 0057): its answer comes later
    assert follow(setup, lambda: {"status": "queued", "job": "J"}) == Pending(Source.SPANSH, "J")
    assert read_cached(setup.database.connection(), Source.ARDENT, "route") is None


def test_a_job_s_result_is_kept_under_its_request(setup: Setup) -> None:
    assert follow(setup, lambda: {"status": "ok", "value": 7}, refresh=True) == Found(
        7, Source.ARDENT, NOW
    )
    # Asked again: the result kept, nothing sent
    assert follow(setup, down) == Found(7, Source.ARDENT, NOW)


def test_a_job_with_the_source_down_is_the_failure(setup: Setup) -> None:
    assert follow(setup, down) == Failed(Source.ARDENT, Unavailable.DOWN)
