"""The Mining tab's calls (ADR 0040): each waits for the sources' answer (``waiting.py``).
Where to sell is the Trade handler's ``find_markets``, shared by both tabs."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from edrockmaster.application.mining_search import MiningSearch
from edrockmaster.desktop.handlers.context import CoreContext
from edrockmaster.desktop.handlers.waiting import Done, wait_for_sources
from edrockmaster.desktop.market_view import refresh
from edrockmaster.desktop.mining_view import (
    estimate_view,
    hotspot_query,
    hotspots_view,
    options_view,
    refused,
)
from edrockmaster.domain.ships import needed_pad


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
        return wait_for_sources(self._context, start, lambda: refused(answer_kind, "down"))
