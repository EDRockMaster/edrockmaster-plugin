"""Use cases of the bounty hunting assistant."""

from __future__ import annotations

from edrockmaster.application.ports import Clock
from edrockmaster.domain.bounty.hunting import (
    HuntingNotification,
    HuntingTracker,
    HuntStats,
    Vouchers,
)
from edrockmaster.domain.bounty.journal import CommunityGoal, parse_entry
from edrockmaster.domain.journal_reading import Entry


class HuntingService:
    """Called on EDMC's main thread only; pure computation."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._tracker = HuntingTracker()

    @property
    def current_stats(self) -> HuntStats | None:
        session = self._tracker.session
        return session.stats if session is not None else None

    @property
    def vouchers(self) -> Vouchers:
        return self._tracker.vouchers

    @property
    def community_goals(self) -> tuple[CommunityGoal, ...]:
        return self._tracker.community_goals

    def handle_journal_entry(self, entry: Entry) -> list[HuntingNotification]:
        fact = parse_entry(entry)
        return self._tracker.handle(fact) if fact is not None else []

    def reset_session(self) -> list[HuntingNotification]:
        ended = self._tracker.reset(self._clock.now())
        return [ended] if ended is not None else []
