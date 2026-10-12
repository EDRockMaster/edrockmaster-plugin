"""The Mining tab's calls (ADR 0040): each waits for the sources' answer, on the caller's thread.

pywebview runs each call of the page on a thread of its own: a search may wait
there, while its work runs on the core thread and the sources on the I/O thread.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import Future
from typing import Any

from edrockmaster.application.mining_search import MiningSearch
from edrockmaster.desktop.handlers.context import CoreContext
from edrockmaster.desktop.mining_view import (
    buyers_view,
    estimate_view,
    hotspot_query,
    hotspots_view,
    options_view,
    refresh,
    refused,
    sale_query,
)
from edrockmaster.domain.ships import needed_pad

SEARCH_TIMEOUT = 60.0
"""Seconds a search waits for its sources (one second apart, 15 at most each)."""

type Done = Callable[[dict[str, Any]], None]


class MiningHandler:
    def __init__(self, context: CoreContext, search: MiningSearch) -> None:
        self._context = context
        self._search = search

    def mining_options(self) -> dict[str, Any]:
        """What the tab's forms start from. Reads immutable objects only: any thread."""
        companion = self._context.companion()
        situation = companion.situation.situation
        pad = needed_pad(situation.ship.symbol) if situation.ship else None
        return options_view(situation.system, pad, companion.settings.sources, self._context.tl)

    def find_hotspots(self, request: Mapping[str, Any]) -> dict[str, Any]:
        try:
            query = hotspot_query(request)
        except ValueError as error:
            self._context.logger.warning("Hotspot search refused: %s", error)
            return refused("hotspots", "invalid")
        return self._wait(
            "hotspots",
            lambda done: self._search.find_hotspots(
                query,
                lambda answer: done(hotspots_view(answer, self._context.tl)),
                refresh=refresh(request),
            ),
        )

    def find_buyers(self, request: Mapping[str, Any]) -> dict[str, Any]:
        try:
            query = sale_query(request)
        except ValueError as error:
            self._context.logger.warning("Market search refused: %s", error)
            return refused("buyers", "invalid")
        return self._wait(
            "buyers",
            lambda done: self._search.find_buyers(
                query, lambda answer: done(buyers_view(answer)), refresh=refresh(request)
            ),
        )

    def estimate_cargo(self) -> dict[str, Any]:
        """The unsold cargo of the mining session, at the best market around the system."""

        def start(done: Done) -> None:
            companion = self._context.companion()
            situation = companion.situation.situation
            if situation.system is None:
                done(refused("estimate", "noSystem"))
                return
            stats = companion.mining.current_stats
            cargo = {c.key: tons for c, tons in (stats.unsold_tons if stats else {}).items()}
            if not cargo:
                done(refused("estimate", "empty"))
                return
            system = situation.system
            self._search.estimate_cargo(
                cargo,
                system,
                needed_pad(situation.ship.symbol) if situation.ship else None,
                lambda answer: done(estimate_view(answer, system, self._context.tl)),
            )

        return self._wait("estimate", start)

    def _wait(self, answer_kind: str, start: Callable[[Done], None]) -> dict[str, Any]:
        """Run ``start`` on the core thread, and wait for the view it hands to ``done``; an empty
        ``answer_kind`` answer if it does not come in time."""
        answer: Future[dict[str, Any]] = Future()

        def job() -> None:
            try:
                start(answer.set_result)
            except Exception as error:
                answer.set_exception(error)

        self._context.on_core(job)
        try:
            return answer.result(timeout=SEARCH_TIMEOUT)
        except TimeoutError:
            self._context.logger.warning("No answer from the sources in %.0f s", SEARCH_TIMEOUT)
            return refused(answer_kind, "down")
