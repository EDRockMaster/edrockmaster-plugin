import logging
import threading
from datetime import UTC, datetime

import pytest

from edrockmaster.application.updates import (
    UpdateChannel,
    UpdateReady,
    UpdateService,
    UpdateState,
    UpdateStatus,
)
from edrockmaster.desktop.updates import Updates
from tests.application.test_updates import FakeSource

WAIT = 5.0
NOW = datetime(2026, 11, 5, 15, 23, 4, tzinfo=UTC)


class Harness:
    def __init__(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        self.source = FakeSource()
        self.wanted: tuple[bool, UpdateChannel | None] = (True, None)
        self.statuses: list[UpdateStatus] = []
        self.checked = threading.Semaphore(0)
        source_find = self.source.find

        def find(channel: UpdateChannel | None) -> str | None:
            found = source_find(channel)
            self.checked.release()
            return found

        self.source.find = find  # type: ignore[method-assign]
        self.updates = Updates(
            UpdateService(self.source, UpdateChannel.STABLE),
            lambda: self.wanted,
            self.statuses.append,
            logging.getLogger("test"),
            interval=3600,
            now=lambda: NOW,
        )

    def wait_check(self) -> None:
        assert self.checked.acquire(timeout=WAIT)

    @property
    def states(self) -> list[UpdateState]:
        return [status.state for status in self.statuses]

    @property
    def ready(self) -> list[UpdateReady]:
        return [status.ready for status in self.statuses if status.ready is not None]


@pytest.fixture
def harness(caplog: pytest.LogCaptureFixture) -> Harness:
    return Harness(caplog)


def test_a_check_at_start_hands_the_version_ready(
    harness: Harness, caplog: pytest.LogCaptureFixture
) -> None:
    harness.source.latest[UpdateChannel.STABLE] = "0.7.1"
    harness.updates.start()
    harness.wait_check()
    harness.updates.stop()
    assert harness.states == [UpdateState.CHECKING, UpdateState.DOWNLOADING, UpdateState.READY]
    assert harness.statuses[-1] == UpdateStatus(UpdateState.READY, NOW, None, UpdateReady("0.7.1"))
    assert harness.updates.status == harness.statuses[-1]
    assert "Update 0.7.1 downloaded, applied at exit or on restart" in caplog.text


def test_nothing_new_is_up_to_date_and_says_when_it_was_checked(harness: Harness) -> None:
    harness.updates.start()
    harness.wait_check()
    harness.updates.stop()
    assert harness.states == [UpdateState.CHECKING, UpdateState.UP_TO_DATE]
    assert harness.statuses[-1].checked_at == NOW


def test_settings_changed_check_again_without_waiting(harness: Harness) -> None:
    harness.updates.start()
    harness.wait_check()
    harness.wanted = (True, UpdateChannel.BETA)
    harness.updates.check_now()
    harness.wait_check()
    harness.updates.stop()
    assert harness.source.asked == [UpdateChannel.STABLE, UpdateChannel.BETA]


def test_a_failed_check_is_told_with_its_reason(
    harness: Harness, caplog: pytest.LogCaptureFixture
) -> None:
    def fail(channel: UpdateChannel | None) -> str | None:
        harness.checked.release()
        raise RuntimeError("os error 32")

    harness.source.find = fail  # type: ignore[method-assign]
    harness.updates.start()
    harness.wait_check()
    harness.updates.stop()
    assert "Could not check for updates: os error 32" in caplog.text
    assert harness.states == [UpdateState.CHECKING, UpdateState.FAILED]
    assert harness.statuses[-1] == UpdateStatus(UpdateState.FAILED, NOW, "os error 32")
    assert harness.ready == []


def test_a_failure_keeps_the_version_already_ready(harness: Harness) -> None:
    harness.source.latest[UpdateChannel.STABLE] = "0.7.1"
    harness.updates.start()
    harness.wait_check()

    def fail(channel: UpdateChannel | None) -> str | None:
        harness.checked.release()
        raise RuntimeError("no network")

    harness.source.find = fail  # type: ignore[method-assign]
    harness.updates.check_now()
    harness.wait_check()
    harness.updates.stop()
    assert harness.statuses[-1].state is UpdateState.FAILED
    assert harness.statuses[-1].ready == UpdateReady("0.7.1")
    assert harness.updates.restart()


def test_a_check_with_a_version_already_ready_stays_ready(harness: Harness) -> None:
    harness.source.latest[UpdateChannel.STABLE] = "0.7.1"
    harness.updates.start()
    harness.wait_check()
    harness.updates.check_now()
    harness.wait_check()
    harness.updates.stop()
    assert harness.statuses[-1].state is UpdateState.READY
    assert harness.statuses[-1].ready == UpdateReady("0.7.1")


def test_off_checks_nothing(harness: Harness, caplog: pytest.LogCaptureFixture) -> None:
    harness.wanted = (False, None)
    harness.updates.start()
    harness.updates.check_now()
    harness.updates.stop()
    assert harness.source.asked == []
    assert UpdateState.CHECKING not in harness.states


def test_restart_then_exit_apply_once(harness: Harness) -> None:
    assert not harness.updates.restart()
    harness.source.latest[UpdateChannel.STABLE] = "0.7.1"
    harness.updates.start()
    harness.wait_check()
    harness.updates.stop()
    assert harness.updates.restart()
    harness.updates.at_exit()
    assert harness.source.applied == [True]


def test_a_version_ready_is_applied_at_exit(harness: Harness) -> None:
    harness.source.latest[UpdateChannel.STABLE] = "0.7.1"
    harness.updates.start()
    harness.wait_check()
    harness.updates.stop()
    harness.updates.at_exit()
    assert harness.source.applied == [False]
