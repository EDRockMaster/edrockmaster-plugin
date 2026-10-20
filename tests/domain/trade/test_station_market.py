"""The market of the station the commander is docked at (ADR 0047), from the last market
opened there."""

from datetime import UTC, datetime, timedelta

from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.trade.journal import (
    CommanderDied,
    Docked,
    GameClosed,
    GameLoaded,
    Market,
    MarketLine,
    MarketRead,
    Undocked,
)
from edrockmaster.domain.trade.station_market import (
    StationMarket,
    StationMarketChanged,
    StationMarketTracker,
)

AT = datetime(2026, 10, 20, 18, 0, tzinfo=UTC)
AMANO = Market(4300769795, "Amano Terminal", "Ngalinn")
GOLD = MarketLine(Commodity("gold"), buy_price=46000, sell_price=45500, stock=1200, demand=0)
WATER = MarketLine(Commodity("water"), buy_price=0, sell_price=420, stock=0, demand=5000)
NOT_TRADED = MarketLine(Commodity("bauxite"), buy_price=626, sell_price=625, stock=0, demand=0)


def opened(tracker: StationMarketTracker) -> StationMarket:
    [changed] = tracker.handle(MarketRead(AT, AMANO, (GOLD, NOT_TRADED, WATER)))
    assert changed.market is not None
    return changed.market


def test_the_market_opened_keeps_what_the_station_sells_or_buys() -> None:
    tracker = StationMarketTracker()
    market = opened(tracker)
    # A commodity with neither stock nor demand is not traded there
    assert market == StationMarket(AMANO, AT, (GOLD, WATER))
    assert tracker.market == market


def test_the_market_goes_once_the_commander_leaves() -> None:
    for leaving in (
        Undocked(AT),
        CommanderDied(AT),
        GameClosed(AT),
        GameLoaded(AT, None),
        GameLoaded(AT, Market(1)),
        Docked(AT, Market(1)),
    ):
        tracker = StationMarketTracker()
        opened(tracker)
        assert tracker.handle(leaving) == [StationMarketChanged(None)]
        assert tracker.market is None
        assert tracker.handle(leaving) == []  # nothing left to forget


def test_the_market_stays_while_docked_there() -> None:
    tracker = StationMarketTracker()
    market = opened(tracker)
    later = AT + timedelta(minutes=1)
    assert tracker.handle(Docked(later, AMANO)) == []
    assert tracker.handle(GameLoaded(later, AMANO)) == []
    assert tracker.market == market
