"""The galaxy's prices of a commodity (ADR 0047): one answer for every commodity, from which the
search picks the one chosen."""

from datetime import UTC, datetime

from edrockmaster.application.community import Answer, Failed, Found, Source, Unavailable
from edrockmaster.application.market_search import MarketSearch
from edrockmaster.domain.commodities import GalaxyPrices, PriceRange
from tests.fakes import FakeMarkets, FixedClock

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
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


def test_a_failed_source_is_passed_on() -> None:
    markets = FakeMarkets({}, Failed(Source.ARDENT, Unavailable.OFF))
    assert prices_of(markets, "gold") == Failed(Source.ARDENT, Unavailable.OFF)
