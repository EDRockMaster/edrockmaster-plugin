from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.domain.mining.markets import (
    CargoEstimate,
    CargoLine,
    MarketOffer,
    SaleQuery,
    select_offers,
)
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
    demand=95,
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
    query = SaleQuery("painite", "Borann")
    assert select_offers([ORBIS, OUTPOST, CARRIER, OLD, FAR], query, NOW) == (OUTPOST, ORBIS)


def test_carriers_far_and_old_markets_when_asked() -> None:
    query = SaleQuery(
        "painite", "Borann", max_distance=100, carriers=True, max_age=timedelta(days=60)
    )
    assert [offer.station for offer in select_offers([ORBIS, CARRIER, OLD, FAR], query, NOW)] == [
        "XHG-10J",
        "Far",
        "Old",
        "Borisenko's Folly",
    ]


def test_only_the_pads_the_ship_can_use() -> None:
    query = SaleQuery("painite", "Borann", needed_pad=PadSize.LARGE)
    assert select_offers([ORBIS, OUTPOST], query, NOW) == (ORBIS,)
    unknown = replace(OUTPOST, pad=None)
    assert select_offers([unknown], query, NOW) == ()


def test_a_sale_query_keeps_its_bounds() -> None:
    with pytest.raises(ValueError, match="system"):
        SaleQuery("painite", "")
    with pytest.raises(ValueError, match="commodity"):
        SaleQuery("", "Borann")
    with pytest.raises(ValueError, match="distance"):
        SaleQuery("painite", "Borann", max_distance=501)
    assert SaleQuery(" painite ", " Borann ").reference == "Borann"


def test_a_cargo_estimate_adds_up_the_lines_priced() -> None:
    estimate = CargoEstimate(
        (
            CargoLine("painite", 10, ORBIS),
            CargoLine("platinum", 4, None),
            CargoLine("opal", 2, OUTPOST),
        )
    )
    assert [line.value for line in estimate.lines] == [912540, None, 240000]
    assert estimate.total == 1152540
    assert CargoEstimate(()).total == 0
