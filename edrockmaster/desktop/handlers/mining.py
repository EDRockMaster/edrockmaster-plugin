"""The Mining tab's calls (ADR 0040): each waits for the sources' answer (``waiting.py``).
Where to sell and the cargo's worth are the Trade handler's, shared by both tabs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from edrockmaster.application.mining_search import MiningSearch
from edrockmaster.desktop.handlers.context import CoreContext
from edrockmaster.desktop.handlers.waiting import wait_for_sources
from edrockmaster.desktop.market_view import refresh
from edrockmaster.desktop.mining_view import (
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
            return refused("invalid")
        return wait_for_sources(
            self._context,
            lambda done: self._search.find_hotspots(
                query,
                lambda answer: done(hotspots_view(answer, self._context.tl)),
                refresh=refresh(request),
            ),
            lambda: refused("down"),
        )
