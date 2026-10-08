"""Entry point of the application layer: the activities, composed (ADR 0011).

``Companion`` records the journal once, hands every entry to each activity and
owns what they share: the settings and the journal recorder.
"""

from __future__ import annotations

from typing import assert_never

from edrockmaster.application.activity import Activity
from edrockmaster.application.combat_service import CombatService
from edrockmaster.application.engineering_service import EngineeringService
from edrockmaster.application.mining_service import MiningNotification, MiningService
from edrockmaster.application.ports import (
    Clock,
    GoalRepository,
    JournalRecorder,
    Notifier,
    SettingsStore,
)
from edrockmaster.application.settings import PluginSettings
from edrockmaster.application.situation_service import SituationService
from edrockmaster.application.trade_service import TradeService
from edrockmaster.domain.combat.session import CombatNotification
from edrockmaster.domain.engineering.catalogue import Catalogue
from edrockmaster.domain.engineering.session import EngineeringNotification
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.situation.situation import SituationChanged
from edrockmaster.domain.trade.session import TradeNotification

type Notification = (
    MiningNotification
    | CombatNotification
    | TradeNotification
    | EngineeringNotification
    | SituationChanged
)
"""What the presentation layer is told after each use case."""


class Companion:
    """Called on EDMC's main thread only; the ports must not block."""

    def __init__(  # noqa: PLR0913 - the ports of every activity
        self,
        *,
        settings_store: SettingsStore,
        notifier: Notifier,
        recorder: JournalRecorder,
        clock: Clock,
        catalogue: Catalogue,
        goals: GoalRepository,
    ) -> None:
        self._store = settings_store
        self._recorder = recorder
        self._settings = settings_store.load()
        self.mining = MiningService(self._settings, notifier, clock)
        self.combat = CombatService(clock)
        self.trade = TradeService(clock)
        self.engineering = EngineeringService(catalogue, goals, clock)
        self.situation = SituationService()

    @property
    def settings(self) -> PluginSettings:
        return self._settings

    def handle_journal_entry(self, entry: Entry, is_beta: bool) -> list[Notification]:
        if self._settings.record_journal:
            self._recorder.record(entry, is_beta)
        notifications: list[Notification] = []
        notifications += self.mining.handle_journal_entry(entry, is_beta)
        notifications += self.combat.handle_journal_entry(entry)
        notifications += self.trade.handle_journal_entry(entry)
        notifications += self.engineering.handle_journal_entry(entry)
        notifications += self.situation.handle_journal_entry(entry)
        return notifications

    def reset(self, activity: Activity) -> list[Notification]:
        """End the running session of one activity (the panel's reset button)."""
        match activity:
            case Activity.MINING:
                return list(self.mining.reset_session())
            case Activity.COMBAT:
                return list(self.combat.reset_session())
            case Activity.TRADE:
                return list(self.trade.reset_session())
            case Activity.ENGINEERING:
                return list(self.engineering.reset_session())
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(activity)

    def change_settings(self, settings: PluginSettings) -> None:
        if settings == self._settings:
            return
        self._store.save(settings)
        self._settings = settings
        self.mining.apply_settings(settings)
