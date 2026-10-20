"""Spansh's trade route planner, as ``TradeRoutes`` (ADR 0047, ADR 0057).

Spansh publishes no documentation of it: the form below is the one its site sends
(``POST /api/trade/route``), with its defaults for what the application does not ask.
Spansh answers with a job; ``/api/results/<job>`` says ``queued`` until the route is
computed, then gives it. The answers recorded in ``tests/fixtures/sources/`` are the
contract this adapter relies on.

The cache keeps nothing of the player (ADR 0039): a request is known by a digest of its
form, which holds the credits, and Spansh's answer is kept without the parameters it
repeats.
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from edrockmaster.application.community import Pending, Source
from edrockmaster.application.route_planner import RouteProgress
from edrockmaster.domain.ships import PadSize
from edrockmaster.domain.trade.routes import (
    HopCommodity,
    RouteHop,
    RouteQuery,
    RouteStation,
    TradeRoute,
)
from edrockmaster.infrastructure.sources.http import SourceClient
from edrockmaster.infrastructure.sources.source import CommunitySource

ROUTE = "https://spansh.co.uk/api/trade/route"
RESULTS = "https://spansh.co.uk/api/results"
ROUTE_MAX_AGE = timedelta(minutes=15)
_ANY_ARRIVAL = 10_000_000
"""Light seconds from the arrival point: its site's default, no limit."""


def route_form(query: RouteQuery) -> dict[str, str | int]:
    def flag(value: bool) -> int:
        return 1 if value else 0

    return {
        "max_hops": query.max_hops,
        "max_hop_distance": f"{query.max_hop_distance:g}",
        "system": query.system,
        "station": query.station,
        "starting_capital": query.credits,
        "max_cargo": query.cargo_capacity,
        "max_system_distance": _ANY_ARRIVAL,
        "max_price_age": round(query.max_price_age.total_seconds()),
        "requires_large_pad": flag(query.needed_pad is PadSize.LARGE),
        "allow_prohibited": 0,
        "allow_planetary": flag(query.planetary),
        "allow_player_owned": flag(query.carriers),
        "allow_restricted_access": 0,
        "unique": 0,
        "permit": 0,
    }


def _station(item: Mapping[str, Any]) -> RouteStation:
    updated = item.get("market_updated_at")
    return RouteStation(
        station=str(item["station"]),
        system=str(item["system"]),
        arrival=item.get("distance_to_arrival"),
        prices_updated=datetime.fromtimestamp(int(updated), UTC) if updated else None,
    )


def _hop(item: Mapping[str, Any]) -> RouteHop:
    return RouteHop(
        source=_station(item["source"]),
        destination=_station(item["destination"]),
        distance=float(item["distance"]),
        commodities=tuple(
            HopCommodity(
                name=str(goods["name"]),
                tons=int(goods["amount"]),
                buy_price=int(goods["source_commodity"]["buy_price"]),
                sell_price=int(goods["destination_commodity"]["sell_price"]),
                profit=int(goods["profit"]),
            )
            for goods in item["commodities"]
        ),
        profit=int(item["total_profit"]),
    )


def read_route_answer(answer: Mapping[str, Any]) -> TradeRoute | Pending:
    """The route, or the job still queued or computed."""
    status = answer["status"]
    if status == "queued":
        return Pending(Source.SPANSH, str(answer["job"]))
    if status != "ok":
        raise ValueError(f"route status {status!r}")
    hops: Sequence[Mapping[str, Any]] = answer["result"]
    return TradeRoute(tuple(_hop(hop) for hop in hops))


class SpanshRoutes:
    def __init__(self, source: CommunitySource, client: SourceClient) -> None:
        self._source = source
        self._client = client

    def plan(
        self,
        query: RouteQuery,
        on_answer: Callable[[RouteProgress], None],
        *,
        refresh: bool = False,
    ) -> None:
        form = route_form(query)
        self._source.follow(
            _request(form),
            lambda: _kept(self._client.post_form(ROUTE, form)),
            read_route_answer,
            ROUTE_MAX_AGE,
            on_answer,
            refresh=refresh,
        )

    def follow(
        self, query: RouteQuery, job: str, on_answer: Callable[[RouteProgress], None]
    ) -> None:
        """The job's result, kept under the query's request once computed."""
        url = f"{RESULTS}/{urllib.parse.quote(job, safe='')}"
        self._source.follow(
            _request(route_form(query)),
            lambda: _kept(self._client.get(url)),
            read_route_answer,
            ROUTE_MAX_AGE,
            on_answer,
            refresh=True,
        )


def _request(form: Mapping[str, str | int]) -> str:
    digest = hashlib.sha256(json.dumps(form, sort_keys=True).encode()).hexdigest()
    return f"{ROUTE} {digest}"


def _kept(answer: Any) -> Any:
    """Spansh's answer without the request's parameters it repeats."""
    if isinstance(answer, Mapping):
        return {key: value for key, value in answer.items() if key != "parameters"}
    return answer
