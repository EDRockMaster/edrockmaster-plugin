"""Use cases of the community goals (ADR 0032): only the journal, nothing stored."""

from __future__ import annotations

from edrockmaster.domain.community_goals.goals import CommunityGoals, CommunityGoalsNotification
from edrockmaster.domain.community_goals.journal import CommunityGoal, parse_entry
from edrockmaster.domain.journal_reading import Entry


class CommunityGoalsService:
    """Called on the core thread only; pure computation."""

    def __init__(self) -> None:
        self._goals = CommunityGoals()

    @property
    def goals(self) -> tuple[CommunityGoal, ...]:
        return self._goals.goals

    def handle_journal_entry(self, entry: Entry) -> list[CommunityGoalsNotification]:
        fact = parse_entry(entry)
        return self._goals.handle(fact) if fact is not None else []
