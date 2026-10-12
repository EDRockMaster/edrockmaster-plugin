"""Use cases of the commander's situation (ADR 0023): only the journal, nothing stored.

The route's alerts (ADR 0043) sound like the other alerts, when sound is on, and
only when the journal line is recent: reading the journal from its start must
not sound the alerts of jumps made long ago.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import timedelta

from edrockmaster.application.ports import Clock, Notifier
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.situation.journal import parse_entry
from edrockmaster.domain.situation.route import RouteAlertRaised, RouteEvent
from edrockmaster.domain.situation.situation import Situation, SituationChanged, SituationTracker

RECENT = timedelta(minutes=1)
"""A journal line younger than this is happening now: its alert sounds."""

type SituationNotification = SituationChanged | RouteEvent


class SituationService:
    """Called on the core's thread only; pure computation."""

    def __init__(
        self,
        notifier: Notifier,
        clock: Clock,
        sound_enabled: Callable[[], bool],
        ship_names: Mapping[str, str] | None = None,
    ) -> None:
        self._tracker = SituationTracker(ship_names)
        self._notifier = notifier
        self._clock = clock
        self._sound_enabled = sound_enabled

    @property
    def situation(self) -> Situation:
        return self._tracker.situation

    def handle_journal_entry(self, entry: Entry) -> list[SituationNotification]:
        fact = parse_entry(entry)
        if fact is None:
            return []
        notifications = self._tracker.handle(fact)
        if self._sound_enabled():
            for raised in notifications:
                if isinstance(raised, RouteAlertRaised) and self._recent(raised):
                    self._notifier.notify(raised)
        return notifications

    def _recent(self, raised: RouteAlertRaised) -> bool:
        return self._clock.now() - raised.at <= RECENT
