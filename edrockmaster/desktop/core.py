"""The desktop application without its window (ADR 0020): journal, core, storage.

``DesktopCore`` is the composition root of the desktop application, as
``edmc/plugin.py`` is the plugin's. It builds the same core (the ``Companion``
of the activities, the local database, the goals, the catalogue), feeds it
with the journal reader instead of EDMC, and pushes the live view to the
interface after each change.

Threads: every call to the companion and to the presenter happens on the
**core thread**, fed by a queue: the journal reader's thread and the
interface's calls only submit jobs to it. The I/O thread of ADR 0018 does the
disk work. ``push`` is called on the core thread and must not block.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from edrockmaster import VERSION
from edrockmaster.application.activity import Activity
from edrockmaster.application.build import BuildInfo
from edrockmaster.application.companion import Companion, Notification
from edrockmaster.application.ports import Clock
from edrockmaster.desktop.journal_reader import POLL_SECONDS, JournalFollower, JournalWatcher
from edrockmaster.desktop.live_view import live_view
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.infrastructure.build_file import load_build
from edrockmaster.infrastructure.catalogue_file import load_catalogue
from edrockmaster.infrastructure.clock import SystemClock
from edrockmaster.infrastructure.database import FILE_NAME as DATABASE_FILE_NAME
from edrockmaster.infrastructure.database import LocalDatabase, Opening
from edrockmaster.infrastructure.goal_repository import SqliteGoalRepository
from edrockmaster.infrastructure.recorder_jsonl import JsonlJournalRecorder
from edrockmaster.infrastructure.settings_edmc import EdmcSettingsStore
from edrockmaster.infrastructure.settings_file import FILE_NAME as SETTINGS_FILE_NAME
from edrockmaster.infrastructure.settings_file import JsonFileConfig
from edrockmaster.infrastructure.sound import SoundNotifier
from edrockmaster.infrastructure.strings_catalogue import number_format, translator
from edrockmaster.infrastructure.worker import IoWorker
from edrockmaster.ui.engineering_names import EngineeringNames
from edrockmaster.ui.panel_model import LocalDataNotice
from edrockmaster.ui.presenter import ActivityPresenter

if sys.platform == "win32":  # pragma: no cover
    import winsound

CORE_THREAD = "EDRockMaster core"
PACKAGE_DIRECTORY = Path(__file__).resolve().parents[1]

type Push = Callable[[dict[str, Any]], None]
"""Sends the live view to the interface; called on the core thread, must not block."""


def _alert_sound() -> None:  # pragma: no cover - the sound of the platform
    if sys.platform == "win32":
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)


class DesktopCore:
    def __init__(  # noqa: PLR0913 - the adapters of a composition root
        self,
        *,
        data_directory: Path,
        journal_folder: Path | None,
        push: Push,
        language: str,
        logger: logging.Logger,
        clock: Clock | None = None,
        poll_interval: float = POLL_SECONDS,
    ) -> None:
        self._data = data_directory
        self._journal_folder = journal_folder
        self._push = push
        self._language = language
        self._logger = logger
        self._clock = clock or SystemClock()
        self._poll_interval = poll_interval
        self._io = IoWorker(logger)
        self._core = IoWorker(logger, CORE_THREAD)
        self._tl = translator(language)
        self._presenter = ActivityPresenter(self._tl, number_format(language))
        self._companion: Companion | None = None
        self._database: LocalDatabase | None = None
        self._follower: JournalFollower | None = None
        self._watcher: JournalWatcher | None = None
        self._notice: LocalDataNotice | None = None
        self.build: BuildInfo = load_build(PACKAGE_DIRECTORY, VERSION, logger)

    @property
    def companion(self) -> Companion | None:
        return self._companion

    @property
    def database(self) -> LocalDatabase | None:
        return self._database

    def start(self) -> None:
        build = self.build
        self._logger.info(
            "EDRockMaster %s (%s, commit %s) starting, journal in %s",
            build.version,
            build.channel.value,
            build.short_commit or "unknown",
            self._journal_folder,
        )
        self._io.start()
        self._core.start()
        database = self._database = LocalDatabase(self._data / DATABASE_FILE_NAME, self._logger)
        self._io.submit(lambda: self._opened(database.open()))
        catalogue = load_catalogue()
        companion = self._companion = Companion(
            settings_store=EdmcSettingsStore(
                JsonFileConfig(self._data / SETTINGS_FILE_NAME, self._io.submit, self._logger),
                self._logger,
            ),
            notifier=SoundNotifier(_alert_sound, self._logger),
            recorder=JsonlJournalRecorder(
                self._data / "recordings", self._io.submit, self._clock.now(), build.version
            ),
            clock=self._clock,
            catalogue=catalogue,
            goals=SqliteGoalRepository(database, self._io.submit, self._core.submit, self._logger),
        )
        self._presenter = ActivityPresenter(
            self._tl,
            number_format(self._language),
            companion.settings.display,
            EngineeringNames(catalogue, self._tl, companion.engineering.name_of),
        )
        companion.engineering.load_goals(self._apply)
        if self._journal_folder is not None:
            follower = self._follower = JournalFollower(
                self._journal_folder, self._on_entry, self._logger
            )
            self._watcher = JournalWatcher(follower, self._logger, self._poll_interval)
            self._watcher.start()
        else:
            self._logger.warning("No journal folder found: nothing to read")

    def stop(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
        self._core.stop()
        if self._database is not None:
            self._io.submit(self._database.close)
        self._io.stop()
        self._logger.info("EDRockMaster stopped")

    # Calls from the interface, from any thread

    def ready(self) -> None:
        """The interface is loaded: it wants the current view."""
        self._logger.info("The interface is ready")
        self._core.submit(self._send)

    def reset(self, activity: str) -> None:
        """A reset button: ends the session of that activity."""
        try:
            chosen = Activity(activity)
        except ValueError:
            self._logger.warning("Reset of an unknown activity %r", activity)
            return
        self._core.submit(lambda: self._apply(self._require_companion().reset(chosen)))

    def dismiss_notice(self) -> None:
        self._core.submit(lambda: self._set_notice(None))

    # The core thread

    def _on_entry(self, entry: Entry, is_beta: bool) -> None:
        """From the journal reader's thread: queued for the core thread."""
        self._core.submit(lambda: self._handle(entry, is_beta))

    def _handle(self, entry: Entry, is_beta: bool) -> None:
        try:
            notifications = self._require_companion().handle_journal_entry(entry, is_beta)
        except Exception:
            self._logger.exception("Could not handle the journal entry %r", entry.get("event"))
            return
        self._apply(notifications)

    def _apply(self, notifications: Sequence[Notification]) -> None:
        if notifications:
            self._presenter.apply(notifications)
            self._send()

    def _opened(self, opening: Opening) -> None:
        """On the I/O thread: how the local database opened (ADR 0018)."""
        if opening.moved_aside is not None:
            notice = LocalDataNotice.RESET
        elif not opening.available:
            notice = LocalDataNotice.UNAVAILABLE
        else:
            return
        self._core.submit(lambda: self._set_notice(notice))

    def _set_notice(self, notice: LocalDataNotice | None) -> None:
        self._notice = notice
        self._send()

    def _send(self) -> None:
        companion = self._require_companion()
        self._presenter.configure(companion.settings.display)
        view = live_view(
            language=self._language,
            current=self._presenter.current.value,
            blocks=self._presenter.blocks_of(companion.settings.display.activities),
            notice=self._notice,
            journal_folder=self._journal_folder,
            journal_file=self._follower.current_file if self._follower else None,
        )
        try:
            self._push(view)
        except Exception:
            self._logger.exception("Could not send the live view to the interface")

    def _require_companion(self) -> Companion:
        if self._companion is None:
            raise RuntimeError("the desktop core has not started")
        return self._companion
