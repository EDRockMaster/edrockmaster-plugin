"""What a cargo is worth at the best markets around (ADR 0040, ADR 0047)."""

from datetime import UTC, datetime, timedelta

from edrockmaster.domain.commodities import CargoEstimate, CargoLine, MarketOffer
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
OUTPOST = MarketOffer(
    station="Stevens Enterprise",
    system="Arouca",
    market_id=1,
    station_type="CraterPort",
    pad=PadSize.MEDIUM,
    arrival=83.9,
    price=120000,
    volume=95,
    distance=20.4,
    updated=NOW - timedelta(hours=2),
    is_carrier=False,
)


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
