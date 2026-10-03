"""Use cases of the mining assistant."""

from __future__ import annotations

from edrockmaster.application.ports import Clock, JournalRecorder, Notifier, SettingsStore
from edrockmaster.application.settings import PluginSettings
from edrockmaster.domain.journal import AsteroidProspected, Entry, parse_entry
from edrockmaster.domain.prospecting import ProspectingMonitor, ProspectorAlertRaised
from edrockmaster.domain.session import MiningTracker, SessionNotification, SessionStats

type MiningNotification = SessionNotification | ProspectorAlertRaised
"""What the presentation layer is told after each use case."""


class MiningService:
    """Entry point of the application layer: one method per use case.

    Called on EDMC's main thread only. Every call is pure computation; the
    ports it uses must hand any slow work over to the I/O thread.
    """

    def __init__(
        self,
        settings_store: SettingsStore,
        notifier: Notifier,
        recorder: JournalRecorder,
        clock: Clock,
    ) -> None:
        self._store = settings_store
        self._notifier = notifier
        self._recorder = recorder
        self._clock = clock
        self._settings = settings_store.load()
        self._tracker = MiningTracker()
        self._monitor = ProspectingMonitor(self._settings.alerts)

    @property
    def settings(self) -> PluginSettings:
        return self._settings

    @property
    def current_stats(self) -> SessionStats | None:
        session = self._tracker.session
        return session.stats if session is not None else None

    @property
    def is_live(self) -> bool:
        return self._tracker.is_live

    def handle_journal_entry(self, entry: Entry, is_beta: bool) -> list[MiningNotification]:
        if self._settings.record_journal:
            self._recorder.record(entry, is_beta)
        self._tracker.set_beta(is_beta)
        fact = parse_entry(entry)
        if fact is None:
            return []
        notifications: list[MiningNotification] = list(self._tracker.handle(fact))
        if isinstance(fact, AsteroidProspected):
            raised = self._monitor.evaluate(fact)
            if raised is not None:
                notifications.append(raised)
                if self._settings.sound_enabled:
                    self._notifier.notify(raised)
        return notifications

    def reset_session(self) -> list[MiningNotification]:
        ended = self._tracker.reset(self._clock.now())
        return [ended] if ended is not None else []

    def change_settings(self, settings: PluginSettings) -> None:
        if settings == self._settings:
            return
        self._store.save(settings)
        self._settings = settings
        self._monitor.update_settings(settings.alerts)
