"""A call that waits for the community sources' answer, on the caller's thread (ADR 0039, ADR
0041).

pywebview runs each call of the page on a thread of its own: a search may wait
there, while its work runs on the core thread and the sources on the I/O thread.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future
from typing import Any

from edrockmaster.desktop.handlers.context import CoreContext

SEARCH_TIMEOUT = 60.0
"""Seconds a search waits for its sources (one second apart, 15 at most each)."""

type Done = Callable[[dict[str, Any]], None]


def wait_for_sources(
    context: CoreContext, start: Callable[[Done], None], silent: Callable[[], dict[str, Any]]
) -> dict[str, Any]:
    """Run ``start`` on the core thread, and wait for the view it hands to ``done``; ``silent()``
    if it does not come in time. A failure of the work fails the call."""
    answer: Future[dict[str, Any]] = Future()

    def job() -> None:
        try:
            start(answer.set_result)
        except Exception as error:
            answer.set_exception(error)

    context.on_core(job)
    try:
        return answer.result(timeout=SEARCH_TIMEOUT)
    except TimeoutError:
        context.logger.warning("No answer from the sources in %.0f s", SEARCH_TIMEOUT)
        return silent()
