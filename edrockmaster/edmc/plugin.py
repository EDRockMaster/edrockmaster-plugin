"""Wiring between EDMC's hooks and the plugin's application layer.

``Plugin`` is the composition root: it builds the adapters, the application
service and the I/O thread, and turns EDMC's hooks into use cases.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from edrockmaster import VERSION
from edrockmaster.application.mining_service import MiningNotification, MiningService
from edrockmaster.application.ports import Clock
from edrockmaster.edmc.i18n import tl
from edrockmaster.infrastructure.clock import SystemClock
from edrockmaster.infrastructure.paths import data_directory as default_data_directory
from edrockmaster.infrastructure.recorder_jsonl import JsonlJournalRecorder
from edrockmaster.infrastructure.settings_edmc import EdmcConfig, EdmcSettingsStore
from edrockmaster.infrastructure.sound import SoundNotifier
from edrockmaster.infrastructure.worker import IoWorker

try:  # pragma: no cover - only available inside EDMC
    from config import appname  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - outside EDMC (tests, tooling)
    appname = "EDMarketConnector"

PLUGIN_NAME = "EDRockMaster"

type Listener = Callable[[Sequence[MiningNotification]], None]
"""Receives the notifications of each use case, on the main thread (the UI)."""


def plugin_logger_name(application: str, module_file: Path) -> str:
    """Name of the logger EDMC sets up for this plugin: ``<appname>.<plugin folder>``.

    This module lives in ``<plugin folder>/edrockmaster/edmc/``.
    """
    return f"{application}.{module_file.resolve().parents[2].name}"


logger = logging.getLogger(plugin_logger_name(appname, Path(__file__)))


def _internal_error() -> str:
    return tl("EDRockMaster: internal error, see the EDMC log")


class Plugin:
    """The plugin as seen by EDMC. All methods run on EDMC's main thread."""

    def __init__(
        self,
        config: EdmcConfig,
        data_directory: Callable[[], Path] = default_data_directory,
        clock: Clock | None = None,
    ) -> None:
        self._config = config
        self._data_directory = data_directory
        self._clock = clock or SystemClock()
        self._worker = IoWorker(logger)
        self._service: MiningService | None = None
        self._listeners: list[Listener] = []
        self._play_alert: Callable[[], None] | None = None

    @property
    def service(self) -> MiningService | None:
        return self._service

    def start(self, plugin_dir: str | os.PathLike[str]) -> str:
        logger.info("EDRockMaster %s started from %s", VERSION, plugin_dir)
        self._worker.start()
        recorder = JsonlJournalRecorder(
            self._data_directory() / "recordings", self._worker.submit, self._clock.now()
        )
        self._service = MiningService(
            settings_store=EdmcSettingsStore(self._config, logger),
            notifier=SoundNotifier(self._alert_sound, logger),
            recorder=recorder,
            clock=self._clock,
        )
        return PLUGIN_NAME

    def stop(self) -> None:
        self._worker.stop()
        logger.info("EDRockMaster stopped")

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def attach_alert_sound(self, play: Callable[[], None]) -> None:
        """Set how alerts are played; needs a widget, so it comes with the UI."""
        self._play_alert = play

    def journal_entry(
        self,
        cmdr: str,
        is_beta: bool,
        system: str | None,
        station: str | None,
        entry: Mapping[str, Any],
        state: Mapping[str, Any],
    ) -> str | None:
        if self._service is None:
            return None
        try:
            notifications = self._service.handle_journal_entry(entry, is_beta)
        except Exception:
            logger.exception("Could not handle the journal entry %r", entry.get("event"))
            return _internal_error()
        return self._publish(notifications)

    def _publish(self, notifications: Sequence[MiningNotification]) -> str | None:
        if not notifications:
            return None
        error = None
        for listener in list(self._listeners):
            # One failing listener must not deprive the others
            try:
                listener(notifications)
            except Exception:
                logger.exception("A listener failed on %r", notifications)
                error = _internal_error()
        return error

    def _alert_sound(self) -> None:
        if self._play_alert is not None:
            self._play_alert()
