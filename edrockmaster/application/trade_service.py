"""Use cases of the trade assistant (ADR 0014)."""

from __future__ import annotations

from edrockmaster.application.ports import Clock
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.trade.journal import parse_entry
from edrockmaster.domain.trade.session import TradeNotification, TradeStats, TradeTracker


class TradeService:
    """Called on the core thread only; pure computation."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._tracker = TradeTracker()

    @property
    def current_stats(self) -> TradeStats | None:
        return self._tracker.stats

    def handle_journal_entry(self, entry: Entry) -> list[TradeNotification]:
        fact = parse_entry(entry)
        return self._tracker.handle(fact) if fact is not None else []

    def reset_session(self) -> list[TradeNotification]:
        ended = self._tracker.reset(self._clock.now())
        return [ended] if ended is not None else []
