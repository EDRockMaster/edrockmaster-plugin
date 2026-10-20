"""A trade route's request and its hops (ADR 0047, ADR 0057)."""

from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.domain.trade.routes import (
    HopCommodity,
    RouteHop,
    RouteQuery,
    RouteStation,
    TradeRoute,
)

SOL = RouteStation("Abraham Lincoln", "Sol", 505, datetime(2026, 10, 20, tzinfo=UTC))
LHS = RouteStation("Finger Ring", "LHS 149", 2551, None)


def test_a_query_with_the_defaults() -> None:
    query = RouteQuery(" Sol ", " Abraham Lincoln ", cargo_capacity=720, credits=100_000_000)
    assert (query.system, query.station) == ("Sol", "Abraham Lincoln")
    assert (query.max_hops, query.max_hop_distance, query.needed_pad) == (3, 30.0, None)
    assert query.max_price_age == timedelta(days=2)
    assert (query.planetary, query.carriers) == (False, False)


@pytest.mark.parametrize(
    "change",
    [
        {"system": " "},
        {"station": ""},
        {"cargo_capacity": 0},
        {"credits": -1},
        {"max_hops": 0},
        {"max_hops": 11},
        {"max_hop_distance": 0},
        {"max_price_age": timedelta(0)},
    ],
)
def test_a_query_not_valid_is_refused(change: dict[str, object]) -> None:
    fields: dict[str, object] = {
        "system": "Sol",
        "station": "Abraham Lincoln",
        "cargo_capacity": 720,
        "credits": 1000,
        **change,
    }
    with pytest.raises(ValueError, match=r"\w"):
        RouteQuery(**fields)  # type: ignore[arg-type]


def test_a_route_s_profit_is_its_hops_together() -> None:
    fuel = HopCommodity("Hydrogen Fuel", 720, buy_price=85, sell_price=120, profit=35)
    first = RouteHop(SOL, LHS, 29.8, (fuel,), profit=25_200)
    second = RouteHop(LHS, SOL, 29.8, (), profit=19_282_320)
    assert fuel.total_profit == 25_200
    assert TradeRoute((first, second)).profit == 19_307_520
    assert TradeRoute(()).profit == 0
