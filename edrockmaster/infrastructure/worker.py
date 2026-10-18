"""A thread fed by a queue of jobs: the I/O thread, and the core thread (ADR 0020).

The core thread must never wait on a file or the network: such work is
submitted as a job to the I/O thread. The core itself runs the same way, on a
worker of its own, fed by the journal reader and the interface. A thread that
may wait, such as the reader of past journals (ADR 0052), ``call``s a job and
gets its result.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable

type Job = Callable[[], None]

THREAD_NAME = "EDRockMaster I/O"
_CALL_CHECK_SECONDS = 0.1


class WorkerStoppedError(RuntimeError):
    """The worker is not running: a job called will never run."""


class IoWorker:
    """Runs submitted jobs one at a time, in order, on a daemon thread."""

    def __init__(self, logger: logging.Logger, name: str = THREAD_NAME) -> None:
        self._logger = logger
        self._name = name
        self._queue: queue.Queue[Job | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stopping = False

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stopping

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("the I/O worker can only be started once")
        self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
        self._thread.start()

    def submit(self, job: Job) -> None:
        if not self.is_running:
            self._logger.warning("Job dropped: %s is not running", self._name)
            return
        self._queue.put(job)

    def call[T](self, job: Callable[[], T]) -> T:
        """Run a job on the worker and wait for its result, or what it raised.

        Never from the worker's own thread, nor from a thread that must not wait.
        """
        done = threading.Event()
        results: list[T] = []
        errors: list[BaseException] = []

        def run() -> None:
            try:
                results.append(job())
            except BaseException as error:  # handed to the caller
                errors.append(error)
            finally:
                done.set()

        if not self.is_running:
            raise WorkerStoppedError(f"{self._name} is not running")
        self._queue.put(run)
        while not done.wait(_CALL_CHECK_SECONDS):
            if self._thread is None or not self._thread.is_alive():
                raise WorkerStoppedError(f"{self._name} ended before the job ran")
        if errors:
            raise errors[0]
        return results[0]

    def stop(self, timeout: float = 5.0) -> bool:
        """Run the pending jobs, then end the thread. Return whether it has ended."""
        if self._thread is None:
            return True
        if not self._stopping:
            self._stopping = True
            self._queue.put(None)
        self._thread.join(timeout)
        if self._thread.is_alive():
            self._logger.warning("%s still busy after %.1f s", self._name, timeout)
            return False
        return True

    def _run(self) -> None:
        while (job := self._queue.get()) is not None:
            try:
                job()
            except Exception:
                self._logger.exception("A job of %s failed", self._name)
