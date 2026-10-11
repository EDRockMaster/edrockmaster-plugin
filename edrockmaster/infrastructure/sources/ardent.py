"""Ardent Insight, as ``CommodityMarkets`` (ADR 0039, ADR 0040).

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
from edrockmaster.domain.mining.markets import MarketOffer, SaleQuery
from edrockmaster.domain.ships import PadSize
from edrockmaster.infrastructure.sources.http import SourceClient
from edrockmaster.infrastructure.sources.source import CommunitySource

API = "https://api.ardent-insight.com/v2"
MARKETS_MAX_AGE = timedelta(hours=1)
CARRIER = "FleetCarrier"


def nearby_imports(query: SaleQuery) -> str:
    """The address of the markets buying the query's commodity around its system."""
    parameters: dict[str, int | str] = {
        "maxDistance": math.ceil(query.max_distance),
        "maxDaysAgo": max(1, math.ceil(query.max_age / timedelta(days=1))),
        "minVolume": 1,
    }
    if not query.carriers:
        parameters["fleetCarriers"] = "false"
    system = urllib.parse.quote(query.reference, safe="")
    commodity = urllib.parse.quote(query.commodity, safe="")
    return (
        f"{API}/system/name/{system}/commodity/name/{commodity}/nearby/imports?"
        f"{urllib.parse.urlencode(parameters)}"
    )


def read_offers(answer: Sequence[Any]) -> tuple[MarketOffer, ...]:
    return tuple(
        MarketOffer(
            station=str(item["stationName"]),
            system=str(item["systemName"]),
            market_id=int(item["marketId"]),
            station_type=str(item["stationType"]),
            pad=PadSize.from_number(item.get("maxLandingPadSize")),
            arrival=item.get("distanceToArrival"),
            price=int(item["sellPrice"]),
            demand=int(item["demand"]),
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

    def find_buyers(
        self,
        query: SaleQuery,
        on_answer: Callable[[Answer[tuple[MarketOffer, ...]]], None],
        *,
        refresh: bool = False,
    ) -> None:
        url = nearby_imports(query)
        self._source.ask(
            url,
            lambda: self._client.get(url),
            read_offers,
            MARKETS_MAX_AGE,
            on_answer,
            refresh=refresh,
        )
