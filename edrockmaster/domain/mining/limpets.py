"""The limpets on board, and an alert before they run out (ADR 0042)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

DEFAULT_LIMPET_ALERT = 5
"""Limpets on board at which the alert sounds, unless the player chose another number."""


@dataclass(frozen=True, slots=True)
class LimpetAlertRaised:
    at: datetime
    count: int
    """Limpets left on board."""


class LimpetMonitor:
    """Alerts once when the limpets on board fall to the threshold; re-armed once they rise
    above it again (a purchase, a synthesis), or for a new session."""

    def __init__(self, threshold: int | None) -> None:
        self._threshold = _checked(threshold)
        self._armed = True

    def update_threshold(self, threshold: int | None) -> None:
        """A new threshold re-arms the alert; the same one, saved again, does not."""
        if threshold != self._threshold:
            self._threshold = _checked(threshold)
            self._armed = True

    def rearm(self) -> None:
        self._armed = True

    def evaluate(self, count: int, at: datetime) -> LimpetAlertRaised | None:
        if self._threshold is None:
            return None
        if count > self._threshold:
            self._armed = True
            return None
        if not self._armed:
            return None
        self._armed = False
        return LimpetAlertRaised(at, count)


def _checked(threshold: int | None) -> int | None:
    if threshold is not None and threshold < 0:
        raise ValueError("the limpet alert is a number of limpets, 0 or more")
    return threshold
