"""Wiring between EDMC's hooks and the plugin's application layer.

``Plugin`` is the composition root: it builds the adapters, the application
service (the ``Companion`` of the activities) and the I/O thread, and turns
EDMC's hooks into use cases.
"""

from __future__ import annotations

import logging
import os
import tkinter as tk
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from edrockmaster import VERSION
from edrockmaster.application.activity import Activity
from edrockmaster.application.companion import Companion, Notification
from edrockmaster.application.ports import Clock
from edrockmaster.edmc import host
from edrockmaster.edmc.i18n import tl
from edrockmaster.infrastructure.clock import SystemClock
from edrockmaster.infrastructure.paths import data_directory as default_data_directory
from edrockmaster.infrastructure.recorder_jsonl import JsonlJournalRecorder
from edrockmaster.infrastructure.settings_edmc import EdmcConfig, EdmcSettingsStore
from edrockmaster.infrastructure.sound import SoundNotifier, system_alert_sound
from edrockmaster.infrastructure.worker import IoWorker
from edrockmaster.ui.panel import Panel
from edrockmaster.ui.preferences import PreferencesTab
from edrockmaster.ui.preferences_form import (
    settings_from_values,
    threshold_rows,
    values_from_settings,
)
from edrockmaster.ui.presenter import ActivityPresenter

try:  # pragma: no cover - only available inside EDMC
    from config import appname  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - outside EDMC (tests, tooling)
    appname = "EDMarketConnector"

PLUGIN_NAME = "EDRockMaster"

type Listener = Callable[[Sequence[Notification]], None]
"""Receives the notifications of each use case, on the main thread (the UI)."""


def plugin_logger_name(application: str, module_file: Path) -> str:
    """Name of the logger EDMC sets up for this plugin: ``<appname>.<plugin folder>``.

    This module lives in ``<plugin folder>/edrockmaster/edmc/``.
    """
    return f"{application}.{module_file.resolve().parents[2].name}"


logger = logging.getLogger(plugin_logger_name(appname, Path(__file__)))


def _internal_error() -> str:
    return tl("EDRockMaster: internal error, see the EDMC log")


def _open_folder(folder: Path) -> None:
    webbrowser.open(folder.as_uri())


class Plugin:
    """The plugin as seen by EDMC. All methods run on EDMC's main thread."""

    def __init__(
        self,
        config: EdmcConfig,
        data_directory: Callable[[], Path] = default_data_directory,
        clock: Clock | None = None,
        open_folder: Callable[[Path], None] = _open_folder,
    ) -> None:
        self._config = config
        self._data_directory = data_directory
        self._clock = clock or SystemClock()
        self._open_folder = open_folder
        self._presenter = ActivityPresenter(tl, host.format_number)
        self._panel: Panel | None = None
        self._tab: PreferencesTab | None = None
        self._worker = IoWorker(logger)
        self._companion: Companion | None = None
        self._listeners: list[Listener] = []
        self._play_alert: Callable[[], None] | None = None

    @property
    def companion(self) -> Companion | None:
        return self._companion

    def start(self, plugin_dir: str | os.PathLike[str]) -> str:
        logger.info("EDRockMaster %s started from %s", VERSION, plugin_dir)
        self._worker.start()
        recorder = JsonlJournalRecorder(
            self._data_directory() / "recordings", self._worker.submit, self._clock.now()
        )
        self._companion = Companion(
            settings_store=EdmcSettingsStore(self._config, logger),
            notifier=SoundNotifier(self._alert_sound, logger),
            recorder=recorder,
            clock=self._clock,
        )
        return PLUGIN_NAME

    def stop(self) -> None:
        self._worker.stop()
        logger.info("EDRockMaster stopped")

    def app(self, parent: tk.Misc) -> tk.Frame:
        """``plugin_app``: the panel in EDMC's main window."""
        if self._companion is not None:
            self._presenter.configure(self._companion.settings.display)
        panel = self._panel = Panel(parent, self.reset_session, tl, host.theme_update)
        panel.render(self._presenter.blocks())
        self.subscribe(self._refresh)
        self.attach_alert_sound(system_alert_sound(panel.frame))
        return panel.frame

    def prefs(self, parent: tk.Misc) -> tk.Widget:
        """``plugin_prefs``: the plugin's tab in EDMC's settings dialog."""
        if self._companion is None:
            raise RuntimeError("the plugin has not started")
        settings = self._companion.settings
        self._tab = PreferencesTab(
            parent,
            values_from_settings(settings, host.format_number),
            threshold_rows(settings, tl),
            tl,
            self.open_recordings,
        )
        frame: tk.Widget = self._tab.frame
        return frame

    def prefs_changed(self) -> None:
        """``prefs_changed``: apply the tab's entries, refresh texts (the language may change)."""
        tab, self._tab = self._tab, None
        if tab is not None and self._companion is not None:
            settings, invalid = settings_from_values(
                tab.values(), self._companion.settings, host.parse_number, tl
            )
            self._companion.change_settings(settings)
            self._presenter.configure(settings.display)
            if invalid:
                host.show_error(
                    tl("Invalid entries ignored: {fields}").format(fields=", ".join(invalid))
                )
        if self._panel is not None:
            self._panel.retranslate()
            self._panel.render(self._presenter.blocks())

    def reset_session(self, activity: Activity) -> None:
        """A reset button of the panel: ends the session of its activity."""
        if self._companion is not None:
            self._publish(self._companion.reset(activity))

    def open_recordings(self) -> None:
        folder = self._data_directory() / "recordings"
        folder.mkdir(parents=True, exist_ok=True)
        self._open_folder(folder)

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
        if self._companion is None:
            return None
        try:
            notifications = self._companion.handle_journal_entry(entry, is_beta)
        except Exception:
            logger.exception("Could not handle the journal entry %r", entry.get("event"))
            return _internal_error()
        return self._publish(notifications)

    def _publish(self, notifications: Sequence[Notification]) -> str | None:
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

    def _refresh(self, notifications: Sequence[Notification]) -> None:
        self._presenter.apply(notifications)
        if self._panel is not None:
            self._panel.render(self._presenter.blocks())

    def _alert_sound(self) -> None:
        if self._play_alert is not None:
            self._play_alert()
