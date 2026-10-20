from datetime import timedelta

import pytest

from edrockmaster.application.trade_service import TradeService
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.trade.session import (
    TradeEnded,
    TradeEndReason,
    TradeStarted,
    TradeUpdated,
)
from edrockmaster.domain.trade.station_market import StationMarketChanged
from tests.fakes import FixedClock
from tests.journal_entries import T0, market_buy_entry, timestamp


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(T0 + timedelta(hours=1))


@pytest.fixture
def service(clock: FixedClock) -> TradeService:
    return TradeService(clock)


def test_a_purchase_starts_a_trade_session(service: TradeService) -> None:
    notifications = service.handle_journal_entry(market_buy_entry(0))
    assert [type(n) for n in notifications] == [TradeStarted, TradeUpdated]
    stats = service.current_stats
    assert stats is not None
    assert stats.cargo.credits == 500_000


def test_irrelevant_entries_produce_nothing(service: TradeService) -> None:
    entry: Entry = {"timestamp": timestamp(0), "event": "Music"}
    assert service.handle_journal_entry(entry) == []
    assert service.current_stats is None


def test_reset_ends_the_session_at_the_clock_time(service: TradeService, clock: FixedClock) -> None:
    service.handle_journal_entry(market_buy_entry(0))
    [ended] = service.reset_session()
    assert isinstance(ended, TradeEnded)
    assert (ended.at, ended.reason) == (clock.current, TradeEndReason.MANUAL)
    assert service.current_stats is None
    assert service.reset_session() == []


def test_the_station_s_market_once_opened_until_undocked(service: TradeService) -> None:
    item = {"Name": "$gold_name;", "BuyPrice": 46000, "SellPrice": 45500, "Stock": 9, "Demand": 0}
    market: Entry = {
        "timestamp": timestamp(0),
        "event": "Market",
        "MarketID": 1,
        "StationName": "Amano Terminal",
        "StarSystem": "Ngalinn",
        "Items": [item],
    }
    [opened] = service.handle_journal_entry(market)
    assert isinstance(opened, StationMarketChanged)
    assert service.station_market == opened.market
    undocked: Entry = {"timestamp": timestamp(60), "event": "Undocked", "MarketID": 1}
    assert service.handle_journal_entry(undocked) == [StationMarketChanged(None)]
    assert service.station_market is None
