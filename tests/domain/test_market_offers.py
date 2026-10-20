"""Market offers both ways (ADR 0040, ADR 0047): the filters the sources cannot apply."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.domain.commodities import MarketOffer, MarketQuery, Side, select_offers
from edrockmaster.domain.ships import PadSize

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
ORBIS = MarketOffer(
    station="Borisenko's Folly",
    system="Arouca",
    market_id=3539221504,
    station_type="CraterPort",
    pad=PadSize.LARGE,
    arrival=83.9,
    price=91254,
    volume=95,
    distance=20.4,
    updated=NOW - timedelta(hours=2),
    is_carrier=False,
)
OUTPOST = replace(
    ORBIS, station="Stevens Enterprise", market_id=1, pad=PadSize.MEDIUM, price=120000
)
CARRIER = replace(
    ORBIS,
    station="XHG-10J",
    market_id=2,
    station_type="FleetCarrier",
    price=300000,
    is_carrier=True,
)
OLD = replace(ORBIS, station="Old", market_id=3, price=200000, updated=NOW - timedelta(days=31))
FAR = replace(ORBIS, station="Far", market_id=4, price=250000, distance=80.0)


def test_the_best_price_first_within_the_query() -> None:
    query = MarketQuery(Side.SELL, "painite", "Borann")
    assert select_offers([ORBIS, OUTPOST, CARRIER, OLD, FAR], query, NOW) == (OUTPOST, ORBIS)


def test_carriers_far_and_old_markets_when_asked() -> None:
    query = MarketQuery(
        Side.SELL, "painite", "Borann", max_distance=100, carriers=True, max_age=timedelta(days=60)
    )
    assert [offer.station for offer in select_offers([ORBIS, CARRIER, OLD, FAR], query, NOW)] == [
        "XHG-10J",
        "Far",
        "Old",
        "Borisenko's Folly",
    ]


def test_only_the_pads_the_ship_can_use() -> None:
    query = MarketQuery(Side.SELL, "painite", "Borann", needed_pad=PadSize.LARGE)
    assert select_offers([ORBIS, OUTPOST], query, NOW) == (ORBIS,)
    unknown = replace(OUTPOST, pad=None)
    assert select_offers([unknown], query, NOW) == ()


def test_a_market_query_keeps_its_bounds() -> None:
    with pytest.raises(ValueError, match="system"):
        MarketQuery(Side.SELL, "painite", "")
    with pytest.raises(ValueError, match="commodity"):
        MarketQuery(Side.SELL, "", "Borann")
    with pytest.raises(ValueError, match="distance"):
        MarketQuery(Side.SELL, "painite", "Borann", max_distance=501)
    assert MarketQuery(Side.SELL, " painite ", " Borann ").reference == "Borann"
    with pytest.raises(ValueError, match="volume"):
        MarketQuery(Side.BUY, "gold", "Sol", min_volume=0)


def test_where_to_buy_the_lowest_price_first() -> None:
    query = MarketQuery(Side.BUY, "gold", "Sol", carriers=True)
    assert select_offers([ORBIS, OUTPOST, CARRIER], query, NOW) == (ORBIS, OUTPOST, CARRIER)


def test_a_demand_or_stock_too_small_is_left_out() -> None:
    query = MarketQuery(Side.BUY, "gold", "Sol", min_volume=100)
    big = replace(OUTPOST, volume=100)
    assert select_offers([ORBIS, big], query, NOW) == (big,)
