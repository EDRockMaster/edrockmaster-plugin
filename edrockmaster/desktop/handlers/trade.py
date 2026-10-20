"""The Trade tab's calls (ADR 0047), and where to buy and sell for both tabs: each search waits
for the sources' answer (``waiting.py``), as do the galaxy's prices."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from edrockmaster.application.community import Failed, Source, Unavailable
from edrockmaster.application.market_search import MarketSearch
from edrockmaster.desktop.handlers.context import CoreContext
from edrockmaster.desktop.handlers.waiting import wait_for_sources
from edrockmaster.desktop.market_view import (
    market_query,
    markets_refused,
    markets_view,
    refresh,
    text,
)
from edrockmaster.desktop.trade_view import (
    options_view,
    prices_refused,
    prices_view,
    station_market_view,
)
from edrockmaster.domain.ships import needed_pad
from edrockmaster.domain.trade.catalogue import CommodityCatalogue


class TradeHandler:
    def __init__(
        self, context: CoreContext, catalogue: CommodityCatalogue, markets: MarketSearch
    ) -> None:
        self._context = context
        self._catalogue = catalogue
        self._markets = markets

    def trade_options(self) -> dict[str, Any]:
        """What the tab's forms start from. Reads immutable objects only: any thread."""
        companion = self._context.companion()
        ship = companion.situation.situation.ship
        return options_view(
            self._catalogue,
            system=companion.situation.situation.system,
            pad=needed_pad(ship.symbol) if ship else None,
            cargo_capacity=ship.cargo_capacity if ship else None,
            sources=companion.settings.sources,
            translate=self._context.tl,
        )

    def find_markets(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Where to buy (``side: buy``) or sell (``side: sell``) a commodity."""
        try:
            query = market_query(request)
        except ValueError as error:
            self._context.logger.warning("Market search refused: %s", error)
            return markets_refused("invalid")
        return wait_for_sources(
            self._context,
            lambda done: self._markets.find_offers(
                query, lambda answer: done(markets_view(answer)), refresh=refresh(request)
            ),
            lambda: markets_refused("down"),
        )

    def galaxy_prices(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """A commodity's lowest, average and highest prices across the galaxy."""
        try:
            commodity = text(request, "commodity")
        except ValueError as error:
            self._context.logger.warning("Prices refused: %s", error)
            return prices_refused("invalid")
        return wait_for_sources(
            self._context,
            lambda done: self._markets.find_prices(
                commodity, lambda answer: done(prices_view(answer)), refresh=refresh(request)
            ),
            lambda: prices_refused("down"),
        )

    def station_market(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """The market of the station the commander is docked at, once opened; with
        ``compare``, each price's gap with the galaxy's average (one answer for all)."""
        market = self._context.companion().trade.station_market
        if market is None or request.get("compare") is not True:
            return station_market_view(market, self._catalogue, None, self._context.tl)
        return wait_for_sources(
            self._context,
            lambda done: self._markets.find_galaxy_prices(
                lambda answer: done(
                    station_market_view(market, self._catalogue, answer, self._context.tl)
                ),
                refresh=refresh(request),
            ),
            lambda: station_market_view(
                market, self._catalogue, Failed(Source.ARDENT, Unavailable.DOWN), self._context.tl
            ),
        )
