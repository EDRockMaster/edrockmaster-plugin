"""The plugin's single I/O thread.

Hooks run on EDMC's tkinter main thread and must never wait on a file or the
network: such work is submitted here as a job. Jobs never touch tkinter.
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

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
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
        self._thread = threading.Thread(target=self._run, name=THREAD_NAME, daemon=True)
        self._thread.start()

    def submit(self, job: Job) -> None:
        if not self.is_running:
            self._logger.warning("I/O job dropped: the worker is not running")
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
            self._logger.warning("I/O worker still busy after %.1f s", timeout)
            return False
        return True

    def _run(self) -> None:
        while (job := self._queue.get()) is not None:
            try:
                job()
            except Exception:
                self._logger.exception("I/O job failed")
