"""When the installed application looks for its updates (ADR 0053).

A thread of its own checks at start, then every 24 hours, and again when the player
changes the update settings: a download must hold neither the core nor the I/O
thread. A version ready goes to the core, which shows it. Applying it waits for the
application to quit, or for the player to restart it.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from edrockmaster.application.updates import UpdateChannel, UpdateReady, UpdateService

UPDATES_THREAD = "EDRockMaster updates"
CHECK_SECONDS = 24 * 60 * 60

type Wanted = Callable[[], tuple[bool, UpdateChannel | None]]
"""Whether the player wants updates, and the channel chosen (``None``: the build's)."""


class Updates:
    def __init__(
        self,
        service: UpdateService,
        wanted: Wanted,
        on_ready: Callable[[UpdateReady], None],
        logger: logging.Logger,
        interval: float = CHECK_SECONDS,
    ) -> None:
        self._service = service
        self._wanted = wanted
        self._on_ready = on_ready
        self._logger = logger
        self._interval = interval
        self._lock = threading.Lock()
        """The service is called from the updates thread, and from the window to apply."""
        self._wake = threading.Event()
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name=UPDATES_THREAD, daemon=True)
        self._thread.start()

    def check_now(self) -> None:
        """The update settings changed: check again without waiting a day."""
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

    def _check(self) -> None:
        enabled, chosen = self._wanted()
        try:
            with self._lock:
                ready = self._service.check(enabled=enabled, chosen=chosen)
        except Exception as error:
            self._logger.info("Could not check for updates: %s", error)
            return
        if not enabled:
            self._logger.info("Updates: checking is off")
        elif ready is None:
            self._logger.info("Updates: nothing new")
        else:
            self._logger.info("Update %s downloaded, applied at exit or on restart", ready.version)
            self._on_ready(ready)
