"""Ports of the application layer, implemented by adapters in ``infrastructure``.

The server link of step 1B will add ``UploadQueue`` and ``Authenticator`` here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from edrockmaster.application.settings import PluginSettings
from edrockmaster.domain.journal import Entry
from edrockmaster.domain.prospecting import ProspectorAlertRaised


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
