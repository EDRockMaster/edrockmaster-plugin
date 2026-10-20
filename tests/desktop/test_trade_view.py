"""The galaxy's prices and the station's market, the answers without the core (ADR 0047)."""

from datetime import UTC, datetime

from edrockmaster.application.community import Failed, Found, Source, Unavailable
from edrockmaster.desktop.trade_view import prices_refused, prices_view, station_market_view
from edrockmaster.domain.commodities import Commodity, GalaxyPrices, PriceRange
from edrockmaster.domain.trade.journal import Market, MarketLine
from edrockmaster.domain.trade.station_market import StationMarket
from edrockmaster.infrastructure.commodity_catalogue_file import load_commodities

READ = datetime.fromisoformat("2026-10-20T14:00:00+02:00")


def test_the_prices_both_ways() -> None:
    prices = GalaxyPrices(
        buy=None,
        sell=PriceRange(2064, 56364, 375928),
        computed_at=datetime.fromisoformat("2026-09-07T07:46:13+02:00"),
    )
    assert prices_view(Found(prices, Source.ARDENT, READ, Unavailable.BUSY)) == {
        "status": "found",
        "source": "ardent",
        "readAt": "2026-10-20T12:00:00+00:00",
        "unavailable": "busy",
        "buy": None,
        "sell": {"lowest": 2064, "average": 56364, "highest": 375928},
        "computedAt": datetime(2026, 9, 7, 5, 46, 13, tzinfo=UTC).isoformat(),
    }


def test_a_failed_source_gives_no_prices() -> None:
    assert prices_view(Failed(Source.ARDENT, Unavailable.OFF)) == {
        "status": "off",
        "source": "ardent",
        "readAt": None,
        "unavailable": None,
        "buy": None,
        "sell": None,
        "computedAt": None,
    }
    assert prices_refused("invalid") == {
        "status": "invalid",
        "source": None,
        "readAt": None,
        "unavailable": None,
        "buy": None,
        "sell": None,
        "computedAt": None,
    }


def french(text: str) -> str:
    return {"Gold|commodity": "Or", "Water|commodity": "Eau"}.get(
        text, text.removesuffix("|commodity")
    )


AMANO = StationMarket(
    Market(4300769795, "Amano Terminal", "Ngalinn"),
    READ,
    (
        MarketLine(Commodity("water"), buy_price=0, sell_price=420, stock=0, demand=5000),
        MarketLine(Commodity("gold"), buy_price=47200, sell_price=46900, stock=1200, demand=30),
        MarketLine(Commodity("silver"), buy_price=4800, sell_price=4700, stock=9, demand=0),
        MarketLine(Commodity("unobtainium"), buy_price=1, sell_price=1, stock=1, demand=0),
    ),
)
GALAXY = {
    "gold": GalaxyPrices(
        buy=PriceRange(3800, 40000, 59270), sell=PriceRange(3799, 50000, 282678), computed_at=READ
    ),
    "water": GalaxyPrices(buy=None, sell=None, computed_at=READ),
}


def test_the_station_s_market_by_category_in_the_player_s_language() -> None:
    view = station_market_view(AMANO, load_commodities(), None, french)
    assert view["comparison"] is None
    market = view["market"]
    assert (market["station"], market["system"], market["carrier"]) == (
        "Amano Terminal",
        "Ngalinn",
        False,
    )
    assert market["readAt"] == "2026-10-20T12:00:00+00:00"
    # In the game's order; a commodity the catalogue does not know is left out
    assert [row["category"] for row in market["categories"]] == ["chemicals", "metals"]
    metals = market["categories"][1]["commodities"]
    assert [row["name"] for row in metals] == ["Or", "Silver"]  # by name
    gold = next(row for row in metals if row["commodity"] == "gold")
    assert gold == {
        "commodity": "gold",
        "name": "Or",
        "rare": False,
        "buy": {"price": 47200, "stock": 1200, "gap": None},
        "sell": {"price": 46900, "demand": 30, "gap": None},
    }
    water = market["categories"][0]["commodities"][0]
    assert (water["buy"], water["sell"]["demand"]) == (None, 5000)


def test_the_gaps_with_the_galaxy_s_averages() -> None:
    answer = Found(GALAXY, Source.ARDENT, READ)
    view = station_market_view(AMANO, load_commodities(), answer, french)
    assert view["comparison"] == {
        "status": "found",
        "source": "ardent",
        "readAt": "2026-10-20T12:00:00+00:00",
        "unavailable": None,
    }
    rows = {
        row["commodity"]: row
        for category in view["market"]["categories"]
        for row in category["commodities"]
    }
    assert (rows["gold"]["buy"]["gap"], rows["gold"]["sell"]["gap"]) == (0.18, -0.062)
    assert rows["water"]["sell"]["gap"] is None  # no average known
    assert rows["silver"]["buy"]["gap"] is None  # not in the answer


def test_no_market_while_not_docked_or_not_opened() -> None:
    failed = Failed(Source.ARDENT, Unavailable.OFF)
    assert station_market_view(None, load_commodities(), failed, french) == {
        "market": None,
        "comparison": {"status": "off", "source": "ardent", "readAt": None, "unavailable": None},
    }
