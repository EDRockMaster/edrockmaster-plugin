"""Ardent's nearby importers and exporters, and the galaxy's prices, read from answers recorded
on 11 and 20 October 2026 (ADR 0040, ADR 0047); the prices are six of the 703 commodities."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from edrockmaster.application.community import Answer, Found, Source
from edrockmaster.domain.commodities import (
    GalaxyPrices,
    MarketOffer,
    MarketQuery,
    PriceRange,
    Side,
)
from edrockmaster.domain.ships import PadSize
from edrockmaster.infrastructure.sources.ardent import (
    PRICES,
    PRICES_MAX_AGE,
    ArdentMarkets,
    nearby_markets,
    read_offers,
    read_prices,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "sources"
IMPORTS = FIXTURES / "ardent-nearby-imports-painite-borann-2026-10-11.json"
EXPORTS = FIXTURES / "ardent-nearby-exports-gold-sol-2026-10-20.json"
COMMODITIES = FIXTURES / "ardent-commodities-2026-10-20.json"


def recorded(fixture: Path = IMPORTS) -> Any:
    return json.loads(fixture.read_text(encoding="utf-8"))


def test_the_address_of_the_nearby_importers() -> None:
    assert nearby_markets(MarketQuery(Side.SELL, "painite", "Borann", max_distance=20.5)) == (
        "https://api.ardent-insight.com/v2/system/name/Borann/commodity/name/painite/"
        "nearby/imports?maxDistance=21&maxDaysAgo=30&minVolume=1&fleetCarriers=false"
    )
    with_carriers = nearby_markets(
        MarketQuery(
            Side.SELL,
            "lowtemperaturediamond",
            "HIP 21991",
            carriers=True,
            max_age=timedelta(hours=6),
        )
    )
    assert with_carriers == (
        "https://api.ardent-insight.com/v2/system/name/HIP%2021991/commodity/name/"
        "lowtemperaturediamond/nearby/imports?maxDistance=50&maxDaysAgo=1&minVolume=1"
    )


def test_the_address_of_the_nearby_exporters_with_a_least_stock() -> None:
    assert nearby_markets(MarketQuery(Side.BUY, "gold", "Sol", min_volume=720)) == (
        "https://api.ardent-insight.com/v2/system/name/Sol/commodity/name/gold/"
        "nearby/exports?maxDistance=50&maxDaysAgo=30&minVolume=720&fleetCarriers=false"
    )


def test_the_recorded_answer_gives_the_offers() -> None:
    offers = read_offers(recorded(), Side.SELL)
    assert len(offers) == 6
    first = offers[0]
    assert first == MarketOffer(
        station="Borisenko's Folly",
        system="Arouca",
        market_id=3539221504,
        station_type="CraterPort",
        pad=PadSize.LARGE,
        arrival=83.874867,
        price=91254,
        volume=95,
        distance=20.0,
        updated=datetime(2026, 10, 11, 10, 11, 18, tzinfo=UTC),
        is_carrier=False,
    )
    assert offers[3].pad is PadSize.MEDIUM
    carrier = offers[-1]
    assert (carrier.station, carrier.is_carrier, carrier.price) == ("ABC-123", True, 300459)


def test_the_recorded_exporters_give_what_they_ask_and_their_stock() -> None:
    offers = read_offers(recorded(EXPORTS), Side.BUY)
    assert len(offers) == 6
    assert offers[2] == MarketOffer(
        station="Kramer Drilling Territory",
        system="36 Ophiuchi",
        market_id=offers[2].market_id,
        station_type=offers[2].station_type,
        pad=PadSize.LARGE,
        arrival=offers[2].arrival,
        price=39893,
        volume=216,
        distance=19.0,
        updated=offers[2].updated,
        is_carrier=False,
    )
    carrier = offers[-1]
    assert (carrier.station, carrier.is_carrier, carrier.price, carrier.volume) == (
        "G2M-BQQ",
        True,
        2356,
        1796,
    )


def test_the_recorded_prices_give_each_commodity_s_range() -> None:
    prices = read_prices(recorded(COMMODITIES))
    assert prices["gold"] == GalaxyPrices(
        buy=PriceRange(lowest=3800, average=44779, highest=59270),
        sell=PriceRange(lowest=3799, average=47791, highest=282678),
        computed_at=datetime(2026, 9, 7, 3, 0, 43, 257000, tzinfo=UTC),
    )
    # No market sells painite: it is mined
    assert prices["painite"].buy is None
    assert prices["painite"].sell == PriceRange(2064, 56364, 375928)
    unknown = prices["antimattercontainmentunit"]
    assert (unknown.buy, unknown.sell) == (None, None)
    assert prices["lavianbrandy"].buy == PriceRange(371, 371, 371)


def test_the_recorded_prices_keep_ardent_s_names() -> None:
    # Ardent also knows commodities by their English name; the catalogue's keys are its others
    assert set(read_prices(recorded(COMMODITIES))) == {
        "advanced catalysers",
        "antimattercontainmentunit",
        "gold",
        "lavianbrandy",
        "painite",
        "wreckagecomponents",
    }


class FakeSource:
    def __init__(self) -> None:
        self.ages: list[timedelta] = []

    def ask(
        self, request: str, fetch: Any, parse: Any, max_age: Any, on_answer: Any, **_: Any
    ) -> None:
        self.ages.append(max_age)
        on_answer(Found(parse(fetch()), Source.ARDENT, datetime(2026, 10, 11, tzinfo=UTC)))


class FakeClient:
    def __init__(self, fixture: Path = IMPORTS) -> None:
        self.fixture = fixture
        self.urls: list[str] = []

    def get(self, url: str) -> Any:
        self.urls.append(url)
        return recorded(self.fixture)


def test_the_markets_get_the_address_and_read_the_answer() -> None:
    client = FakeClient()
    answers: list[Answer[tuple[MarketOffer, ...]]] = []
    query = MarketQuery(Side.SELL, "painite", "Borann")
    ArdentMarkets(FakeSource(), client).find_offers(query, answers.append)  # type: ignore[arg-type]
    assert client.urls == [nearby_markets(query)]
    [found] = answers
    assert isinstance(found, Found)
    assert len(found.value) == 6


def test_the_prices_are_asked_in_one_request_kept_a_day() -> None:
    source, client = FakeSource(), FakeClient(COMMODITIES)
    answers: list[Answer[dict[str, GalaxyPrices]]] = []
    ArdentMarkets(source, client).find_prices(answers.append)  # type: ignore[arg-type]
    assert client.urls == [PRICES] == ["https://api.ardent-insight.com/v2/commodities"]
    assert source.ages == [PRICES_MAX_AGE] == [timedelta(days=1)]
    [found] = answers
    assert isinstance(found, Found)
    assert "gold" in found.value
