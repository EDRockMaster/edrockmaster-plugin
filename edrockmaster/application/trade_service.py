"""Use cases of the trade assistant (ADR 0014), and the market of the station the commander is
docked at (ADR 0047)."""

from __future__ import annotations

from edrockmaster.application.ports import Clock
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.trade.journal import parse_entry
from edrockmaster.domain.trade.session import TradeNotification, TradeStats, TradeTracker
from edrockmaster.domain.trade.station_market import (
    StationMarket,
    StationMarketChanged,
    StationMarketTracker,
)

type TradeServiceNotification = TradeNotification | StationMarketChanged


class TradeService:
    """Called on the core thread only; pure computation."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._tracker = TradeTracker()
        self._market = StationMarketTracker()

    @property
    def current_stats(self) -> TradeStats | None:
        return self._tracker.stats

    @property
    def station_market(self) -> StationMarket | None:
        """Immutable: may be read from any thread."""
        return self._market.market

    def handle_journal_entry(self, entry: Entry) -> list[TradeServiceNotification]:
        fact = parse_entry(entry)
        if fact is None:
            return []
        return [*self._tracker.handle(fact), *self._market.handle(fact)]

    def reset_session(self) -> list[TradeNotification]:
        ended = self._tracker.reset(self._clock.now())
        return [ended] if ended is not None else []
