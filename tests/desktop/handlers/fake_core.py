"""A core context that runs each job at once, on a real companion (ADR 0041)."""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from edrockmaster.application.companion import Companion, Notification
from edrockmaster.desktop.handlers.context import CoreContext, Job
from tests.domain.engineering.catalogue_data import catalogue
from tests.fakes import (
    FakeGoalRepository,
    FakeNotifier,
    FakeRecorder,
    FakeSettingsStore,
    FixedClock,
)

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


class FakeCore:
    """What the handlers reach: ``applied`` and ``refreshes`` tell what they did."""

    def __init__(self, language: str = "en") -> None:
        self.companion = Companion(
            settings_store=FakeSettingsStore(),
            notifier=FakeNotifier(),
            recorder=FakeRecorder(),
            clock=FixedClock(NOW),
            catalogue=catalogue(),
            goals=FakeGoalRepository(),
        )
        self.companion.engineering.load_goals(lambda notifications: None)
        self.applied: list[Notification] = []
        self.refreshes = 0
        self.language = language
        self.logger = logging.getLogger("test.handlers")
        self.context = CoreContext(
            on_core=self._run,
            on_io=self._run,
            companion=lambda: self.companion,
            apply=self._apply,
            refresh=self._refresh,
            tl=lambda text: f"{self.language}:{text}",
            language=lambda: self.language,
            clock=FixedClock(NOW),
            logger=self.logger,
        )

    @staticmethod
    def _run(job: Job) -> None:
        job()

    def _apply(self, notifications: Sequence[Notification]) -> None:
        self.applied.extend(notifications)

    def _refresh(self) -> None:
        self.refreshes += 1
