"""The plugin's single I/O thread, and the desktop application's core thread.

Hooks run on EDMC's tkinter main thread and must never wait on a file or the
network: such work is submitted here as a job. Jobs never touch tkinter. The
desktop application runs its core the same way, on a worker of its own
(ADR 0020).
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable

type Job = Callable[[], None]

THREAD_NAME = "EDRockMaster I/O"


class IoWorker:
    """Runs submitted jobs one at a time, in order, on a daemon thread."""

    def __init__(self, logger: logging.Logger, name: str = THREAD_NAME) -> None:
        self._logger = logger
        self._name = name
        self._queue: queue.Queue[Job | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stopping = False

    @property
    def thread(self) -> threading.Thread | None:
        return self._thread

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
