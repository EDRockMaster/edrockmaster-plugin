"""Entry point of the application layer: the activities, composed (ADR 0011).

``Companion`` records the journal once, hands every entry to each activity and
owns what they share: the settings and the journal recorder.
"""

from __future__ import annotations

from edrockmaster.application.activity import Activity
from edrockmaster.application.combat_service import CombatService
from edrockmaster.application.mining_service import MiningNotification, MiningService
from edrockmaster.application.ports import Clock, JournalRecorder, Notifier, SettingsStore
from edrockmaster.application.settings import PluginSettings
from edrockmaster.domain.combat.session import CombatNotification
from edrockmaster.domain.journal_reading import Entry

type Notification = MiningNotification | CombatNotification
"""What the presentation layer is told after each use case."""


class Companion:
    """Called on EDMC's main thread only; the ports must not block."""

    def __init__(
        self,
        settings_store: SettingsStore,
        notifier: Notifier,
        recorder: JournalRecorder,
        clock: Clock,
    ) -> None:
        self._store = settings_store
        self._recorder = recorder
        self._settings = settings_store.load()
        self.mining = MiningService(self._settings, notifier, clock)
        self.combat = CombatService(clock)

    @property
    def settings(self) -> PluginSettings:
        return self._settings

    def handle_journal_entry(self, entry: Entry, is_beta: bool) -> list[Notification]:
        if self._settings.record_journal:
            self._recorder.record(entry, is_beta)
        notifications: list[Notification] = []
        notifications += self.mining.handle_journal_entry(entry, is_beta)
        notifications += self.combat.handle_journal_entry(entry)
        return notifications

    def reset(self, activity: Activity) -> list[Notification]:
        """End the running session of one activity (the panel's reset button)."""
        if activity is Activity.MINING:
            return list(self.mining.reset_session())
        return list(self.combat.reset_session())

    def change_settings(self, settings: PluginSettings) -> None:
        if settings == self._settings:
            return
        self._store.save(settings)
        self._settings = settings
        self.mining.apply_settings(settings)
