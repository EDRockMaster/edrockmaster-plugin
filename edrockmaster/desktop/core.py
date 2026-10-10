"""The desktop application without its window (ADR 0020): journal, core, storage.

``DesktopCore`` is the composition root of the application. It builds the core
(the ``Companion`` of the activities, the local database, the goals, the
catalogue), feeds it with the journal reader, and pushes the live view to the
interface after each change.

Threads: every call to the companion and to the presenter happens on the
**core thread**, fed by a queue: the journal reader's thread and the
interface's calls only submit jobs to it. The I/O thread of ADR 0018 does the
disk work. ``push`` is called on the core thread and must not block.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from edrockmaster import VERSION
from edrockmaster.application.activity import Activity
from edrockmaster.application.build import BuildInfo
from edrockmaster.application.companion import Companion, Notification
from edrockmaster.application.ports import Clock
from edrockmaster.desktop.engineering_view import (
    catalogue_view,
    engineering_view,
    goal_from_request,
    with_count,
)
from edrockmaster.desktop.journal_folder import default_journal_folder
from edrockmaster.desktop.journal_reader import POLL_SECONDS, JournalFollower, JournalWatcher
from edrockmaster.desktop.live_view import live_view
from edrockmaster.desktop.settings_view import (
    DesktopPreferences,
    DesktopPreferencesStore,
    SettingsError,
    settings_from_request,
    settings_view,
)
from edrockmaster.domain.engineering.goals import GoalId
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.infrastructure.build_file import load_build
from edrockmaster.infrastructure.catalogue_file import load_catalogue
from edrockmaster.infrastructure.clock import SystemClock
from edrockmaster.infrastructure.database import FILE_NAME as DATABASE_FILE_NAME
from edrockmaster.infrastructure.database import LocalDatabase, Opening
from edrockmaster.infrastructure.goal_repository import SqliteGoalRepository
from edrockmaster.infrastructure.recorder_jsonl import JsonlJournalRecorder
from edrockmaster.infrastructure.settings_file import FILE_NAME as SETTINGS_FILE_NAME
from edrockmaster.infrastructure.settings_file import JsonFileConfig
from edrockmaster.infrastructure.settings_store import KeyValueSettingsStore
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
        usual_journal_folder: Callable[[], Path | None] = default_journal_folder,
    ) -> None:
        """``journal_folder``: set by the environment, before the settings' and the usual one;
        ``language``: the system's, unless the settings choose another."""
        self._data = data_directory
        self._journal_override = journal_folder
        self._usual_journal_folder = usual_journal_folder
        self._journal_folder: Path | None = journal_folder
        self._push = push
        self._system_language = language
        self._language = language
        self._logger = logger
        self._clock = clock or SystemClock()
        self._poll_interval = poll_interval
        self._io = IoWorker(logger)
        self._core = IoWorker(logger, CORE_THREAD)
        self._translations = translator(language)
        self._number_format = number_format(language)
        self._presenter = ActivityPresenter(self._tl, self._format_number)
        self._preferences = DesktopPreferences()
        self._preferences_store: DesktopPreferencesStore | None = None
        self._companion: Companion | None = None
        self._database: LocalDatabase | None = None
        self._follower: JournalFollower | None = None
        self._watcher: JournalWatcher | None = None
        self._notice: LocalDataNotice | None = None
        self._names: EngineeringNames | None = None
        self._catalogue_view: dict[str, Any] | None = None
        self._interface_ready = False
        """Set once the interface asked for the view: until then, nothing is pushed, since a
        push to a window not yet loaded would wait for it."""
        self.build: BuildInfo = load_build(PACKAGE_DIRECTORY, VERSION, logger)

    @property
    def companion(self) -> Companion | None:
        return self._companion

    @property
    def database(self) -> LocalDatabase | None:
        return self._database

    def start(self) -> None:
        build = self.build
        config = JsonFileConfig(self._data / SETTINGS_FILE_NAME, self._io.submit, self._logger)
        store = self._preferences_store = DesktopPreferencesStore(config)
        preferences = self._preferences = store.load()
        self._set_language(preferences.language)
        self._journal_folder = (
            self._journal_override
            or (Path(preferences.journal_folder) if preferences.journal_folder else None)
            or self._usual_journal_folder()
        )
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
            settings_store=KeyValueSettingsStore(config, self._logger),
            notifier=SoundNotifier(_alert_sound, self._logger),
            recorder=JsonlJournalRecorder(
                self._data / "recordings", self._io.submit, self._clock.now(), build.version
            ),
            clock=self._clock,
            catalogue=catalogue,
            goals=SqliteGoalRepository(database, self._io.submit, self._core.submit, self._logger),
        )
        names = self._names = EngineeringNames(catalogue, self._tl, companion.engineering.name_of)
        self._catalogue_view = catalogue_view(catalogue, EngineeringNames(catalogue, self._tl))
        self._presenter = ActivityPresenter(
            self._tl, self._format_number, companion.settings.display, names
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

        def first_view() -> None:
            self._interface_ready = True
            self._send()

        self._core.submit(first_view)

    def reset(self, activity: str) -> None:
        """A reset button: ends the session of that activity."""
        try:
            chosen = Activity(activity)
        except ValueError:
            self._logger.warning("Reset of an unknown activity %r", activity)
            return

        def reset() -> None:
            notifications = self._require_companion().reset(chosen)
            # Logged: what the player pressed, and whether a session was running
            self._logger.info(
                "Reset of %s: %s", chosen.value, "session ended" if notifications else "no session"
            )
            self._apply(notifications)

        self._core.submit(reset)

    def shown(self) -> None:
        """The interface shows its first live view: the core's pushes reach the page."""
        self._logger.info("The interface shows the live view")

    def dismiss_notice(self) -> None:
        self._core.submit(lambda: self._set_notice(None))

    # Settings

    def settings(self) -> dict[str, Any]:
        """What the settings form shows. Reads immutable objects only: any thread."""
        return settings_view(
            self._require_companion().settings,
            self._preferences,
            self._journal_folder,
            self._tl,
        )

    def save_settings(self, request: Mapping[str, Any]) -> None:
        def save() -> None:
            companion = self._require_companion()
            try:
                settings, preferences = settings_from_request(request, companion.settings)
            except SettingsError as error:
                self._logger.warning("Settings refused: %s", error)
                return
            companion.change_settings(settings)
            if preferences != self._preferences:
                assert self._preferences_store is not None, "created at start, with the companion"
                self._preferences_store.save(preferences)
                if preferences.journal_folder != self._preferences.journal_folder:
                    self._logger.info("Journal folder set, used from the next start")
                self._preferences = preferences
                self._set_language(preferences.language)
            self._presenter.configure(settings.display)
            self._send()

        self._core.submit(save)

    # Engineering goals (ADR 0017)

    def catalogue(self) -> dict[str, Any]:
        """What the goal form offers. Built once at start and never changed: any thread."""
        if self._catalogue_view is None:
            raise RuntimeError("the desktop core has not started")
        return self._catalogue_view

    def add_goal(self, request: Mapping[str, Any]) -> None:
        def add() -> None:
            engineering = self._require_companion().engineering
            try:
                goal = goal_from_request(request, engineering.catalogue)
            except ValueError as error:
                self._logger.warning("Goal refused: %s", error)
                return
            self._apply(engineering.add_goal(goal))

        self._core.submit(add)

    def change_goal(self, goal_id: str, count: int) -> None:
        def change() -> None:
            engineering = self._require_companion().engineering
            goal = next((g for g in engineering.goals if g.id.value == goal_id), None)
            if goal is None:
                self._logger.warning("No goal %r to change", goal_id)
                return
            try:
                changed = with_count(goal, count)
            except (ValueError, TypeError) as error:
                self._logger.warning("Goal change refused: %s", error)
                return
            self._apply(engineering.replace_goal(changed))

        self._core.submit(change)

    def remove_goal(self, goal_id: str) -> None:
        def remove() -> None:
            engineering = self._require_companion().engineering
            if not any(goal.id.value == goal_id for goal in engineering.goals):
                self._logger.warning("No goal %r to remove", goal_id)
                return
            self._apply(engineering.remove_goal(GoalId(goal_id)))

        self._core.submit(remove)

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
        if not self._interface_ready:
            return
        self._presenter.configure(companion.settings.display)
        view = live_view(
            language=self._language,
            current=self._presenter.current.value,
            blocks=self._presenter.blocks_of(companion.settings.display.activities),
            notice=self._notice,
            journal_folder=self._journal_folder,
            journal_file=self._follower.current_file if self._follower else None,
            situation=companion.situation.situation,
            engineering=engineering_view(companion.engineering, self._require_names()),
        )
        try:
            self._push(view)
        except Exception:
            self._logger.exception("Could not send the live view to the interface")

    # Language: the presenters translate through these, so that a change applies at once

    def _tl(self, text: str) -> str:
        return self._translations(text)

    def _format_number(self, number: float, decimals: int) -> str:
        return self._number_format(number, decimals)

    def _set_language(self, choice: str) -> None:
        language = self._system_language if choice == "auto" else choice
        if language == self._language and self._catalogue_view is not None:
            return
        self._language = language
        self._translations = translator(language)
        self._number_format = number_format(language)
        if self._companion is not None:
            catalogue = self._companion.engineering.catalogue
            self._catalogue_view = catalogue_view(catalogue, EngineeringNames(catalogue, self._tl))

    def _require_names(self) -> EngineeringNames:
        if self._names is None:
            raise RuntimeError("the desktop core has not started")
        return self._names

    def _require_companion(self) -> Companion:
        if self._companion is None:
            raise RuntimeError("the desktop core has not started")
        return self._companion
