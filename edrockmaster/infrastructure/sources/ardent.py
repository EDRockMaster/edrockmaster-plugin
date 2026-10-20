"""Ardent Insight, as ``CommodityMarkets`` (ADR 0039, ADR 0040, ADR 0047): the markets that
buy a commodity near a system (``nearby/imports``), and those that sell it (``nearby/exports``).

Its routes are documented in the README of ``github.com/iaincollins/ardent-api``:
anonymous, no rate limit enforced, respectful use appreciated.
"""

from __future__ import annotations

import math
import urllib.parse
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Any

from edrockmaster.application.community import Answer
from edrockmaster.domain.commodities import MarketOffer, MarketQuery, Side
from edrockmaster.domain.ships import PadSize
from edrockmaster.infrastructure.sources.http import SourceClient
from edrockmaster.infrastructure.sources.source import CommunitySource

API = "https://api.ardent-insight.com/v2"
MARKETS_MAX_AGE = timedelta(hours=1)
CARRIER = "FleetCarrier"
_ROUTES = {Side.SELL: "imports", Side.BUY: "exports"}
_PRICES = {Side.SELL: "sellPrice", Side.BUY: "buyPrice"}
"""What the market pays the player, or what it asks of them."""
_VOLUMES = {Side.SELL: "demand", Side.BUY: "stock"}


def nearby_markets(query: MarketQuery) -> str:
    """The address of the markets buying (or selling) the query's commodity around its
    system."""
    parameters: dict[str, int | str] = {
        "maxDistance": math.ceil(query.max_distance),
        "maxDaysAgo": max(1, math.ceil(query.max_age / timedelta(days=1))),
        "minVolume": query.min_volume,
    }
    if not query.carriers:
        parameters["fleetCarriers"] = "false"
    system = urllib.parse.quote(query.reference, safe="")
    commodity = urllib.parse.quote(query.commodity, safe="")
    return (
        f"{API}/system/name/{system}/commodity/name/{commodity}/nearby/{_ROUTES[query.side]}?"
        f"{urllib.parse.urlencode(parameters)}"
    )


def read_offers(answer: Sequence[Any], side: Side) -> tuple[MarketOffer, ...]:
    price, volume = _PRICES[side], _VOLUMES[side]
    return tuple(
        MarketOffer(
            station=str(item["stationName"]),
            system=str(item["systemName"]),
            market_id=int(item["marketId"]),
            station_type=str(item["stationType"]),
            pad=PadSize.from_number(item.get("maxLandingPadSize")),
            arrival=item.get("distanceToArrival"),
            price=int(item[price]),
            volume=int(item[volume]),
            distance=float(item["distance"]),
            updated=datetime.fromisoformat(str(item["updatedAt"])),
            is_carrier=item["stationType"] == CARRIER,
        )
        for item in answer
    )


class ArdentMarkets:
    def __init__(self, source: CommunitySource, client: SourceClient) -> None:
        self._source = source
        self._client = client

    def find_offers(
        self,
        query: MarketQuery,
        on_answer: Callable[[Answer[tuple[MarketOffer, ...]]], None],
        *,
        refresh: bool = False,
    ) -> None:
        url = nearby_markets(query)
        self._source.ask(
            url,
            lambda: self._client.get(url),
            lambda answer: read_offers(answer, query.side),
            MARKETS_MAX_AGE,
            on_answer,
            refresh=refresh,
        )
