"""Use cases of the commander's situation (ADR 0023): only the journal, nothing stored."""

from __future__ import annotations

from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.situation.journal import parse_entry
from edrockmaster.domain.situation.situation import Situation, SituationChanged, SituationTracker


class SituationService:
    """Called on the core's thread only; pure computation."""

    def __init__(self) -> None:
        self._tracker = SituationTracker()

    @property
    def situation(self) -> Situation:
        return self._tracker.situation

    def handle_journal_entry(self, entry: Entry) -> list[SituationChanged]:
        fact = parse_entry(entry)
        return self._tracker.handle(fact) if fact is not None else []
