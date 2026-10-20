"""Where to mine, where to buy and sell, and the cargo's worth (ADR 0040, ADR 0047), with
sources that answer at once."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.application.community import Answer, Failed, Found, Source, Unavailable
from edrockmaster.application.market_search import MarketSearch
from edrockmaster.application.mining_search import MiningSearch
from edrockmaster.domain.commodities import MarketOffer, MarketQuery, Side
from edrockmaster.domain.mining.hotspots import HotspotPage, HotspotQuery, hotspot_commodity
from edrockmaster.domain.mining.markets import CargoEstimate, CargoLine
from edrockmaster.domain.ships import PadSize
from tests.fakes import FixedClock

NOW = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
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


class FakeCatalogue:
    def __init__(self) -> None:
        self.asked: list[tuple[HotspotQuery, bool]] = []

    def find_hotspots(
        self,
        query: HotspotQuery,
        on_answer: Callable[[Answer[HotspotPage]], None],
        *,
        refresh: bool = False,
    ) -> None:
        self.asked.append((query, refresh))
        on_answer(Found(HotspotPage(query, (), 0), Source.SPANSH, READ))


class FakeMarkets:
    def __init__(self, answers: dict[str, Answer[tuple[MarketOffer, ...]]]) -> None:
        self.answers = answers
        self.asked: list[MarketQuery] = []

    def find_offers(
        self,
        query: MarketQuery,
        on_answer: Callable[[Answer[tuple[MarketOffer, ...]]], None],
        *,
        refresh: bool = False,
    ) -> None:
        self.asked.append(query)
        on_answer(self.answers[query.commodity])


def found(*offers: MarketOffer, read_at: datetime = READ) -> Answer[tuple[MarketOffer, ...]]:
    return Found(offers, Source.ARDENT, read_at)


def markets_of(markets: FakeMarkets) -> MarketSearch:
    return MarketSearch(markets, FixedClock(NOW))


def search(markets: FakeMarkets, catalogue: FakeCatalogue | None = None) -> MiningSearch:
    return MiningSearch(catalogue or FakeCatalogue(), markets_of(markets))


def test_hotspots_are_asked_of_the_catalogue() -> None:
    painite = hotspot_commodity("Painite")
    assert painite is not None
    catalogue = FakeCatalogue()
    answers: list[Answer[HotspotPage]] = []
    query = HotspotQuery(painite, "Borann")
    search(FakeMarkets({}), catalogue).find_hotspots(query, answers.append, refresh=True)
    assert catalogue.asked == [(query, True)]
    assert isinstance(answers[0], Found)


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
    search(markets).estimate_cargo(
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
    search(markets).estimate_cargo(
        {"painite": 2, "opal": 1}, "Borann", PadSize.LARGE, answers.append
    )
    [estimate] = answers
    assert isinstance(estimate, Found)
    assert estimate.unavailable is Unavailable.BUSY
    assert estimate.value.total == 2 * OFFER.price


def test_an_estimate_with_no_source_answering_is_the_failure() -> None:
    failed = Failed(Source.ARDENT, Unavailable.OFF)
    answers: list[Answer[CargoEstimate]] = []
    search(FakeMarkets({"painite": failed})).estimate_cargo(
        {"painite": 2}, "Borann", None, answers.append
    )
    assert answers == [failed]


def test_an_empty_cargo_has_nothing_to_estimate() -> None:
    with pytest.raises(ValueError, match="no cargo"):
        search(FakeMarkets({})).estimate_cargo({"painite": 0}, "Borann", None, print)
