"""Where to buy and sell, a cargo's worth (ADR 0040, ADR 0047), and the galaxy's prices: one
answer for every commodity, from which the search picks the one chosen. The sources answer at
once."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.application.community import Answer, Failed, Found, Source, Unavailable
from edrockmaster.application.market_search import MarketSearch
from edrockmaster.domain.commodities import (
    CargoEstimate,
    CargoLine,
    GalaxyPrices,
    MarketOffer,
    MarketQuery,
    PriceRange,
    Side,
)
from edrockmaster.domain.ships import PadSize
from tests.fakes import FakeMarkets, FixedClock

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
READ = NOW - timedelta(minutes=5)

OFFER = MarketOffer(
    station="Borisenko's Folly",
    system="Arouca",
    market_id=1,
    station_type="CraterPort",
    pad=PadSize.LARGE,
    arrival=83.9,
    price=91254,
    volume=95,
    distance=20.0,
    updated=NOW - timedelta(hours=1),
    is_carrier=False,
)
BETTER_MEDIUM = replace(OFFER, station="Outpost", market_id=2, pad=PadSize.MEDIUM, price=120000)
CARRIER = replace(OFFER, station="ABC-123", market_id=3, price=300000, is_carrier=True)


def found(*offers: MarketOffer, read_at: datetime = READ) -> Answer[tuple[MarketOffer, ...]]:
    return Found(offers, Source.ARDENT, read_at)


def markets_of(markets: FakeMarkets) -> MarketSearch:
    return MarketSearch(markets, FixedClock(NOW))


GOLD = GalaxyPrices(
    buy=PriceRange(3800, 44779, 59270),
    sell=PriceRange(3799, 47791, 282678),
    computed_at=datetime(2026, 9, 7, 3, 0, tzinfo=UTC),
)


def prices_of(
    markets: FakeMarkets, commodity: str, *, refresh: bool = False
) -> Answer[GalaxyPrices | None]:
    answers: list[Answer[GalaxyPrices | None]] = []
    MarketSearch(markets, FixedClock(NOW)).find_prices(commodity, answers.append, refresh=refresh)
    [answer] = answers
    return answer


def test_the_prices_of_the_commodity_chosen() -> None:
    markets = FakeMarkets({}, Found({"gold": GOLD}, Source.ARDENT, NOW, Unavailable.BUSY))
    assert prices_of(markets, "gold") == Found(GOLD, Source.ARDENT, NOW, Unavailable.BUSY)
    assert markets.prices_asked == [False]


def test_a_commodity_the_source_does_not_know_has_no_prices() -> None:
    markets = FakeMarkets({}, Found({"gold": GOLD}, Source.ARDENT, NOW))
    assert prices_of(markets, "Painite", refresh=True) == Found(None, Source.ARDENT, NOW)
    assert markets.prices_asked == [True]


def test_a_failed_source_gives_no_prices() -> None:
    markets = FakeMarkets({}, Failed(Source.ARDENT, Unavailable.OFF))
    assert prices_of(markets, "gold") == Failed(Source.ARDENT, Unavailable.OFF)


def test_every_commodity_s_prices_at_once() -> None:
    markets = FakeMarkets({}, Found({"gold": GOLD}, Source.ARDENT, NOW))
    answers: list[Answer[Mapping[str, GalaxyPrices]]] = []
    MarketSearch(markets, FixedClock(NOW)).find_galaxy_prices(answers.append, refresh=True)
    assert answers == [Found({"gold": GOLD}, Source.ARDENT, NOW)]
    assert markets.prices_asked == [True]


def test_the_buyers_are_selected_by_the_domain() -> None:
    markets = FakeMarkets({"painite": found(OFFER, BETTER_MEDIUM, CARRIER)})
    answers: list[Answer[tuple[MarketOffer, ...]]] = []
    query = MarketQuery(Side.SELL, "painite", "Borann", needed_pad=PadSize.LARGE)
    markets_of(markets).find_offers(query, answers.append)
    assert answers == [Found((OFFER,), Source.ARDENT, READ)]


def test_the_sellers_cheapest_first() -> None:
    markets = FakeMarkets({"painite": found(CARRIER, BETTER_MEDIUM, OFFER)})
    answers: list[Answer[tuple[MarketOffer, ...]]] = []
    markets_of(markets).find_offers(MarketQuery(Side.BUY, "painite", "Borann"), answers.append)
    assert answers == [Found((OFFER, BETTER_MEDIUM), Source.ARDENT, READ)]


def test_a_failed_source_is_passed_on() -> None:
    failed = Failed(Source.ARDENT, Unavailable.BUSY)
    answers: list[Answer[tuple[MarketOffer, ...]]] = []
    markets_of(FakeMarkets({"painite": failed})).find_offers(
        MarketQuery(Side.SELL, "painite", "Sol"), answers.append
    )
    assert answers == [failed]


def test_the_cargo_at_the_best_market_for_each_commodity() -> None:
    older = NOW - timedelta(minutes=50)
    markets = FakeMarkets(
        {"painite": found(OFFER, BETTER_MEDIUM), "platinum": found(read_at=older)}
    )
    answers: list[Answer[CargoEstimate]] = []
    markets_of(markets).estimate_cargo(
        {"painite": 10, "platinum": 4, "gold": 0}, "Borann", None, answers.append
    )
    assert [(query.side, query.commodity) for query in markets.asked] == [
        (Side.SELL, "painite"),
        (Side.SELL, "platinum"),
    ]
    [estimate] = answers
    assert estimate == Found(
        CargoEstimate((CargoLine("painite", 10, BETTER_MEDIUM), CargoLine("platinum", 4, None))),
        Source.ARDENT,
        older,
    )


def test_an_estimate_says_when_a_commodity_could_not_be_priced() -> None:
    markets = FakeMarkets(
        {"painite": found(OFFER), "opal": Failed(Source.ARDENT, Unavailable.BUSY)}
    )
    answers: list[Answer[CargoEstimate]] = []
    markets_of(markets).estimate_cargo(
        {"painite": 2, "opal": 1}, "Borann", PadSize.LARGE, answers.append
    )
    [estimate] = answers
    assert isinstance(estimate, Found)
    assert estimate.unavailable is Unavailable.BUSY
    assert estimate.value.total == 2 * OFFER.price


def test_an_estimate_with_no_source_answering_is_the_failure() -> None:
    failed = Failed(Source.ARDENT, Unavailable.OFF)
    answers: list[Answer[CargoEstimate]] = []
    markets_of(FakeMarkets({"painite": failed})).estimate_cargo(
        {"painite": 2}, "Borann", None, answers.append
    )
    assert answers == [failed]


def test_an_empty_cargo_has_nothing_to_estimate() -> None:
    with pytest.raises(ValueError, match="no cargo"):
        markets_of(FakeMarkets({})).estimate_cargo({"painite": 0}, "Borann", None, print)
