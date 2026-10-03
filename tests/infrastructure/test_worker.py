import functools
import logging
import threading
from collections.abc import Iterator

import pytest

from edrockmaster.infrastructure.worker import IoWorker

logger = logging.getLogger("test.worker")


@pytest.fixture
def worker() -> Iterator[IoWorker]:
    worker = IoWorker(logger)
    worker.start()
    yield worker
    worker.stop()


def test_jobs_run_in_order_off_the_calling_thread(worker: IoWorker) -> None:
    seen: list[tuple[int, str]] = []

    def job(number: int) -> None:
        seen.append((number, threading.current_thread().name))

    for number in range(5):
        worker.submit(functools.partial(job, number))
    assert worker.stop()
    assert [number for number, _ in seen] == [0, 1, 2, 3, 4]
    assert all(name == "EDRockMaster I/O" for _, name in seen)


def test_thread_is_a_daemon(worker: IoWorker) -> None:
    assert worker.is_running
    assert worker.thread is not None
    assert worker.thread.daemon


def test_a_failing_job_is_logged_and_does_not_stop_the_worker(
    worker: IoWorker, caplog: pytest.LogCaptureFixture
) -> None:
    done = threading.Event()

    def fail() -> None:
        raise OSError("disk full")

    with caplog.at_level(logging.ERROR):
        worker.submit(fail)
        worker.submit(done.set)
        assert done.wait(timeout=2)
    assert "disk full" in caplog.text


def test_stop_drains_pending_jobs_then_joins(worker: IoWorker) -> None:
    seen: list[int] = []
    worker.submit(lambda: seen.append(1))
    assert worker.stop(timeout=2)
    assert seen == [1]
    assert not worker.is_running


def test_jobs_submitted_after_stop_are_dropped(
    worker: IoWorker, caplog: pytest.LogCaptureFixture
) -> None:
    worker.stop()
    seen: list[int] = []
    with caplog.at_level(logging.WARNING):
        worker.submit(lambda: seen.append(1))
    assert seen == []
    assert "dropped" in caplog.text


def test_stop_is_idempotent(worker: IoWorker) -> None:
    assert worker.stop()
    assert worker.stop()


def test_stop_reports_a_job_that_does_not_finish_in_time() -> None:
    worker = IoWorker(logger)
    worker.start()
    release = threading.Event()

    def busy() -> None:
        release.wait(timeout=5)

    worker.submit(busy)
    assert not worker.stop(timeout=0.05)
    release.set()
    assert worker.stop(timeout=2)


def test_start_twice_is_refused(worker: IoWorker) -> None:
    with pytest.raises(RuntimeError):
        worker.start()


def test_stopping_a_worker_that_never_started_is_harmless() -> None:
    assert IoWorker(logger).stop()
