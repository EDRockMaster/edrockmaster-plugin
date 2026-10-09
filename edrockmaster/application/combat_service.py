"""Use cases of the combat assistant."""

from __future__ import annotations

from edrockmaster.application.ports import Clock
from edrockmaster.domain.combat.journal import CommunityGoal, parse_entry
from edrockmaster.domain.combat.session import (
    CombatNotification,
    CombatStats,
    CombatTracker,
    Vouchers,
)
from edrockmaster.domain.journal_reading import Entry


class CombatService:
    """Called on the core thread only; pure computation."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._tracker = CombatTracker()

    @property
    def current_stats(self) -> CombatStats | None:
        session = self._tracker.session
        return session.stats if session is not None else None

    @property
    def vouchers(self) -> Vouchers:
        return self._tracker.vouchers

    @property
    def community_goals(self) -> tuple[CommunityGoal, ...]:
        return self._tracker.community_goals

    def handle_journal_entry(self, entry: Entry) -> list[CombatNotification]:
        fact = parse_entry(entry)
        return self._tracker.handle(fact) if fact is not None else []

    def reset_session(self) -> list[CombatNotification]:
        ended = self._tracker.reset(self._clock.now())
        return [ended] if ended is not None else []
