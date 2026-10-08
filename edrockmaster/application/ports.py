"""Ports of the application layer, implemented by adapters in ``infrastructure``.

The server link of step 1B will add ``UploadQueue`` and ``Authenticator`` here.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from edrockmaster.application.settings import PluginSettings
from edrockmaster.domain.engineering.goals import Goal, GoalId
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.mining.prospecting import ProspectorAlertRaised


class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current time, timezone-aware (UTC)."""
        ...


class SettingsStore(Protocol):
    def load(self) -> PluginSettings:
        """Return the stored settings, or the defaults for anything missing or invalid."""
        ...

    def save(self, settings: PluginSettings) -> None: ...


class Notifier(Protocol):
    def notify(self, alert: ProspectorAlertRaised) -> None:
        """Draw the player's attention to an alert (sound). Must not block."""
        ...


class JournalRecorder(Protocol):
    def record(self, entry: Entry, is_beta: bool) -> None:
        """Keep a verbatim copy of a journal entry. Must not block."""
        ...


class GoalRepository(Protocol):
    """The player's engineering goals, kept across restarts (ADR 0017, ADR 0018).

    No method blocks: the storage works on the I/O thread. The goals are listed
    in the order they were added.
    """

    def load(self, on_loaded: Callable[[tuple[Goal, ...]], None]) -> None:
        """Read the stored goals; ``on_loaded`` is called later, on the main thread."""
        ...

    def add(self, goal: Goal) -> None: ...

    def replace(self, goal: Goal) -> None:
        """Store a changed goal (its rolls or applications), keeping its place."""
        ...

    def remove(self, goal_id: GoalId) -> None: ...
