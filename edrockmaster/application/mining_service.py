"""Use cases of the mining assistant."""

from __future__ import annotations

from edrockmaster.application.ports import Clock, Notifier
from edrockmaster.application.settings import PluginSettings
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.mining.journal import AsteroidProspected, CargoChanged, parse_entry
from edrockmaster.domain.mining.limpets import LimpetAlertRaised, LimpetMonitor
from edrockmaster.domain.mining.prospecting import ProspectingMonitor, ProspectorAlertRaised
from edrockmaster.domain.mining.session import MiningTracker, SessionNotification, SessionStats

type MiningAlert = ProspectorAlertRaised | LimpetAlertRaised
type MiningNotification = SessionNotification | MiningAlert
"""What the presentation layer is told after each mining use case."""


class MiningService:
    """Called on the core thread only. Every call is pure computation; the
    notifier must hand any slow work over to the I/O thread.
    """

    def __init__(self, settings: PluginSettings, notifier: Notifier, clock: Clock) -> None:
        self._notifier = notifier
        self._clock = clock
        self._settings = settings
        self._tracker = MiningTracker()
        self._monitor = ProspectingMonitor(settings.alerts)
        self._limpets = LimpetMonitor(settings.alerts.limpet_alert)

    @property
    def current_stats(self) -> SessionStats | None:
        session = self._tracker.session
        return session.stats if session is not None else None

    @property
    def is_live(self) -> bool:
        return self._tracker.is_live

    def handle_journal_entry(self, entry: Entry, is_beta: bool) -> list[MiningNotification]:
        self._tracker.set_beta(is_beta)
        fact = parse_entry(entry)
        if fact is None:
            return []
        notifications: list[MiningNotification] = list(self._tracker.handle(fact))
        raised: MiningAlert | None = None
        if isinstance(fact, AsteroidProspected):
            raised = self._monitor.evaluate(fact)
        elif self._tracker.session is None:
            # A new session alerts again for limpets already low (ADR 0042)
            self._limpets.rearm()
        elif isinstance(fact, CargoChanged):
            raised = self._limpets.evaluate(fact.limpets, fact.at)
        if raised is not None:
            notifications.append(raised)
            if self._settings.sound_enabled:
                self._notifier.notify(raised)
        return notifications

    def reset_session(self) -> list[MiningNotification]:
        ended = self._tracker.reset(self._clock.now())
        return [ended] if ended is not None else []

    def apply_settings(self, settings: PluginSettings) -> None:
        self._settings = settings
        self._monitor.update_settings(settings.alerts)
        self._limpets.update_threshold(settings.alerts.limpet_alert)
