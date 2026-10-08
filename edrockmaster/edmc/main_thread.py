"""Results of the I/O thread handed back to EDMC's main thread (ADR 0018).

Tk may only be used from the main thread. The I/O thread puts callbacks in a
queue, and the main thread runs them, polling the queue with ``after()``.
Waking the main thread with ``event_generate()`` from the I/O thread, as EDMC
does for its own threads, needs Tk's main loop to run: EDMC calls ``plugin_app``
before starting it, and the local database opens at that time. Polling makes no
Tk call from the I/O thread at all. Callbacks queued before the panel exists
wait for it.
"""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from collections.abc import Callable

POLL_MS = 100
"""How often the main thread looks for results: unnoticeable, and costs nothing."""

type Callback = Callable[[], None]


class MainThreadDispatcher:
    def __init__(self, logger: logging.Logger, poll_ms: int = POLL_MS) -> None:
        self._logger = logger
        self._poll_ms = poll_ms
        self._pending: queue.SimpleQueue[Callback] = queue.SimpleQueue()
        self._widget: tk.Misc | None = None

    def attach(self, widget: tk.Misc) -> None:
        """Run callbacks in this widget's main loop from now on (main thread)."""
        self._widget = widget
        self._poll()

    def dispatch(self, callback: Callback) -> None:
        """Run ``callback`` later, on the main thread. Safe from any thread."""
        self._pending.put(callback)

    def _poll(self) -> None:
        self._run_pending()
        widget = self._widget
        if widget is None:
            return
        try:
            widget.after(self._poll_ms, self._poll)
        except tk.TclError:  # the widget is gone: EDMC is closing
            self._widget = None

    def _run_pending(self) -> None:
        while True:
            try:
                callback = self._pending.get_nowait()
            except queue.Empty:
                return
            try:
                callback()
            except Exception:
                self._logger.exception("A result of the I/O thread failed on the main thread")
