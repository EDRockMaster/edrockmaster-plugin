import logging
import threading

import pytest

from edrockmaster.application.updates import UpdateChannel, UpdateReady, UpdateService
from edrockmaster.desktop.updates import Updates
from tests.application.test_updates import FakeSource

WAIT = 5.0


class Harness:
    def __init__(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        self.source = FakeSource()
        self.wanted: tuple[bool, UpdateChannel | None] = (True, None)
        self.ready: list[UpdateReady] = []
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
            self.ready.append,
            logging.getLogger("test"),
            interval=3600,
        )

    def wait_check(self) -> None:
        assert self.checked.acquire(timeout=WAIT)


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
    assert harness.ready == [UpdateReady("0.7.1")]
    assert "Update 0.7.1 downloaded, applied at exit or on restart" in caplog.text


def test_settings_changed_check_again_without_waiting(harness: Harness) -> None:
    harness.updates.start()
    harness.wait_check()
    harness.wanted = (True, UpdateChannel.BETA)
    harness.updates.check_now()
    harness.wait_check()
    harness.updates.stop()
    assert harness.source.asked == [UpdateChannel.STABLE, UpdateChannel.BETA]


def test_a_failed_check_is_only_logged(harness: Harness, caplog: pytest.LogCaptureFixture) -> None:
    def fail(channel: UpdateChannel | None) -> str | None:
        harness.checked.release()
        raise RuntimeError("no network")

    harness.source.find = fail  # type: ignore[method-assign]
    harness.updates.start()
    harness.wait_check()
    harness.updates.stop()
    assert "Could not check for updates: no network" in caplog.text
    assert harness.ready == []


def test_off_checks_nothing(harness: Harness, caplog: pytest.LogCaptureFixture) -> None:
    harness.wanted = (False, None)
    harness.updates.start()
    harness.updates.check_now()
    harness.updates.stop()
    assert harness.source.asked == []


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
