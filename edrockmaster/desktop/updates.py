"""When the installed application looks for its updates (ADR 0053).

A thread of its own checks at start, then every 24 hours, and again when the player
changes the update settings or asks to check now: a download must hold neither the core nor
the I/O thread. Each step (checking, downloading, up to date, ready, failed) goes to the core
as an ``UpdateStatus``, which shows it. Applying a version ready waits for the application
to quit, or for the player to restart it.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime

from edrockmaster.application.updates import (
    UpdateChannel,
    UpdateService,
    UpdateState,
    UpdateStatus,
)

UPDATES_THREAD = "EDRockMaster updates"
CHECK_SECONDS = 24 * 60 * 60

type Wanted = Callable[[], tuple[bool, UpdateChannel | None]]
"""Whether the player wants updates, and the channel chosen (``None``: the build's)."""


class Updates:
    def __init__(  # noqa: PLR0913, PLR0917 - the collaborators of a thread, the clock for tests
        self,
        service: UpdateService,
        wanted: Wanted,
        on_status: Callable[[UpdateStatus], None],
        logger: logging.Logger,
        interval: float = CHECK_SECONDS,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._service = service
        self._wanted = wanted
        self._on_status = on_status
        self._logger = logger
        self._interval = interval
        self._now = now
        self._status = UpdateStatus(UpdateState.OFF)
        self._status_lock = threading.Lock()
        self._lock = threading.Lock()
        """The service is called from the updates thread, and from the window to apply."""
        self._wake = threading.Event()
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name=UPDATES_THREAD, daemon=True)
        self._thread.start()

    @property
    def status(self) -> UpdateStatus:
        with self._status_lock:
            return self._status

    def check_now(self) -> None:
        """The player asked, or the update settings changed: check again without waiting a day."""
        self._wake.set()

    def stop(self) -> None:
        self._stopping.set()
        self._wake.set()
        if self._thread is not None:
            # A download under way is dropped: the next start checks again
            self._thread.join(timeout=1.0)

    def restart(self) -> bool:
        """The player restarts to update: ``True`` if the version ready will be applied once the
        application has quit, then started again."""
        with self._lock:
            restarting = self._service.restart()
        if restarting:
            self._logger.info("Restarting to update")
        return restarting

    def at_exit(self) -> None:
        with self._lock:
            ready = self._service.ready
            self._service.at_exit()
        if ready is not None:
            self._logger.info("Update %s applied once the application has quit", ready.version)

    def _run(self) -> None:
        while not self._stopping.is_set():
            self._check()
            self._wake.wait(self._interval)
            self._wake.clear()

    def _publish(
        self, state: UpdateState, *, checked: bool = False, error: str | None = None
    ) -> None:
        with self._status_lock:
            before = self._status
            self._status = UpdateStatus(
                state,
                self._now() if checked else before.checked_at,
                error,
                self._service.ready,
            )
            status = self._status
        self._on_status(status)

    def _check(self) -> None:
        enabled, chosen = self._wanted()
        if enabled:
            self._publish(UpdateState.CHECKING)
        try:
            with self._lock:
                ready = self._service.check(
                    enabled=enabled,
                    chosen=chosen,
                    downloading=lambda: self._publish(UpdateState.DOWNLOADING),
                )
                kept = self._service.ready
        except Exception as error:
            self._logger.info("Could not check for updates: %s", error)
            self._publish(
                UpdateState.FAILED, checked=True, error=str(error) or type(error).__name__
            )
            return
        if not enabled:
            self._logger.info("Updates: checking is off")
            self._publish(UpdateState.OFF)
        elif ready is None:
            self._logger.info("Updates: nothing new")
            self._publish(UpdateState.READY if kept else UpdateState.UP_TO_DATE, checked=True)
        else:
            self._logger.info("Update %s downloaded, applied at exit or on restart", ready.version)
            self._publish(UpdateState.READY, checked=True)
