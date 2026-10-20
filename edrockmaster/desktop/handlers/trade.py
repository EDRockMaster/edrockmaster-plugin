"""The Trade tab's calls (ADR 0047), and where to buy and sell and the cargo's worth for both
tabs: each search waits for the sources' answer (``waiting.py``), as do the galaxy's prices."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from edrockmaster.application.community import Failed, Source, Unavailable
from edrockmaster.application.market_search import MarketSearch
from edrockmaster.application.route_planner import RoutePlanner
from edrockmaster.desktop.handlers.context import CoreContext
from edrockmaster.desktop.handlers.waiting import Done, wait_for_sources
from edrockmaster.desktop.market_view import (
    estimate_refused,
    estimate_view,
    market_query,
    markets_refused,
    markets_view,
    refresh,
    text,
)
from edrockmaster.desktop.trade_view import (
    commodity_name,
    options_view,
    prices_refused,
    prices_view,
    route_query,
    route_refused,
    route_view,
    station_market_view,
)
from edrockmaster.domain.ships import needed_pad
from edrockmaster.domain.trade.catalogue import CommodityCatalogue


class TradeHandler:
    def __init__(
        self,
        context: CoreContext,
        catalogue: CommodityCatalogue,
        markets: MarketSearch,
        routes: RoutePlanner,
    ) -> None:
        self._context = context
        self._catalogue = catalogue
        self._markets = markets
        self._routes = routes

    def trade_options(self) -> dict[str, Any]:
        """What the tab's forms start from. Reads immutable objects only: any thread."""
        companion = self._context.companion()
        ship = companion.situation.situation.ship
        situation = companion.situation.situation
        return options_view(
            self._catalogue,
            system=situation.system,
            station=situation.station,
            pad=needed_pad(ship.symbol) if ship else None,
            cargo_capacity=ship.cargo_capacity if ship else None,
            jump_range=ship.jump_range if ship else None,
            credits=situation.credits,
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

    def estimate_cargo(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """A cargo at the best market around the current system for each commodity: the mining
        session's unsold cargo (``hold: mining``), or all the ship carries that may be sold
        (``hold: ship``)."""
        hold = request.get("hold")
        if hold not in ("mining", "ship"):
            self._context.logger.warning("Estimate refused: hold %r", hold)
            return estimate_refused("invalid")

        def start(done: Done) -> None:
            companion = self._context.companion()
            situation = companion.situation.situation
            if situation.system is None:
                done(estimate_refused("noSystem"))
                return
            if hold == "ship":
                cargo = companion.trade.cargo_to_sell
            else:
                stats = companion.mining.current_stats
                cargo = {c.key: tons for c, tons in (stats.unsold_tons if stats else {}).items()}
            if not any(tons > 0 for tons in cargo.values()):
                done(estimate_refused("empty"))
                return
            system = situation.system
            self._markets.estimate_cargo(
                cargo,
                system,
                needed_pad(situation.ship.symbol) if situation.ship else None,
                lambda answer: done(estimate_view(answer, system, self._name)),
            )

        return wait_for_sources(self._context, start, lambda: estimate_refused("down"))

    def _name(self, key: str) -> str:
        return commodity_name(self._catalogue, key, self._context.tl)

    def plan_route(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Send a trade route's request (ADR 0057): the route if kept, else Spansh's job."""
        try:
            query = route_query(request)
        except ValueError as error:
            self._context.logger.warning("Trade route refused: %s", error)
            return route_refused("invalid")
        return wait_for_sources(
            self._context,
            lambda done: self._routes.plan(
                query,
                lambda progress: done(route_view(progress, self._context.tl)),
                refresh=refresh(request),
            ),
            lambda: route_refused("down"),
        )

    def follow_route(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Ask Spansh once for the route of a job: the interface asks again while pending."""
        try:
            query, job = route_query(request), text(request, "job")
        except ValueError as error:
            self._context.logger.warning("Trade route refused: %s", error)
            return route_refused("invalid")
        return wait_for_sources(
            self._context,
            lambda done: self._routes.follow(
                query, job, lambda progress: done(route_view(progress, self._context.tl))
            ),
            lambda: route_refused("down"),
        )
