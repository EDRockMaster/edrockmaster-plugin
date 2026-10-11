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
from concurrent.futures import Future
from pathlib import Path
from typing import Any

from edrockmaster import VERSION
from edrockmaster.application.activity import Activity
from edrockmaster.application.build import BuildInfo
from edrockmaster.application.community import Source
from edrockmaster.application.companion import Companion, Notification
from edrockmaster.application.mining_search import MiningSearch
from edrockmaster.application.ports import Clock
from edrockmaster.desktop.engineering_view import (
    catalogue_view,
    engineering_view,
    goal_from_request,
    with_count,
)
from edrockmaster.desktop.folder_opener import open_in_file_manager
from edrockmaster.desktop.journal_folder import default_journal_folder
from edrockmaster.desktop.journal_reader import POLL_SECONDS, JournalFollower, JournalWatcher
from edrockmaster.desktop.layout import (
    Layout,
    LayoutError,
    LayoutStore,
    default_layout,
    layout_view,
    view_layout_from_request,
)
from edrockmaster.desktop.live_view import live_view
from edrockmaster.desktop.mining_view import (
    buyers_view,
    estimate_view,
    hotspot_query,
    hotspots_view,
    options_view,
    refresh,
    refused,
    sale_query,
)
from edrockmaster.desktop.settings_view import (
    DesktopPreferences,
    DesktopPreferencesStore,
    SettingsError,
    settings_from_request,
    settings_view,
)
from edrockmaster.domain.engineering.goals import GoalId
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.ships import needed_pad
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
from edrockmaster.infrastructure.ship_names_file import load_ship_names
from edrockmaster.infrastructure.sound import SoundNotifier
from edrockmaster.infrastructure.sources.ardent import ArdentMarkets
from edrockmaster.infrastructure.sources.http import Opener, SourceClient, user_agent
from edrockmaster.infrastructure.sources.http import open_url as default_opener
from edrockmaster.infrastructure.sources.source import CommunitySource
from edrockmaster.infrastructure.sources.spansh import SpanshCatalogue
from edrockmaster.infrastructure.strings_catalogue import number_format, translator
from edrockmaster.infrastructure.worker import IoWorker
from edrockmaster.ui.engineering_names import EngineeringNames
from edrockmaster.ui.panel_model import LocalDataNotice
from edrockmaster.ui.presenter import ActivityPresenter

if sys.platform == "win32":  # pragma: no cover
    import winsound

CORE_THREAD = "EDRockMaster core"
RECORDINGS_DIRECTORY = "recordings"
SEARCH_TIMEOUT = 60.0
"""Seconds a search of the Mining tab waits for its sources (one second apart, 15 at most each)."""
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
        logs_directory: Path | None = None,
        open_folder: Callable[[Path], None] = open_in_file_manager,
        http_opener: Opener = default_opener,
    ) -> None:
        """``journal_folder``: set by the environment, before the settings' and the usual one;
        ``language``: the system's, unless the settings choose another; ``logs_directory``:
        where the log file is, in the data directory unless the demo keeps its data apart."""
        self._data = data_directory
        self._folders = {
            "recordings": data_directory / RECORDINGS_DIRECTORY,
            "logs": logs_directory or data_directory / "logs",
        }
        self._open_folder = open_folder
        self._http_opener = http_opener
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
        self._layout: Layout = default_layout()
        self._layout_store: LayoutStore | None = None
        self._companion: Companion | None = None
        self._database: LocalDatabase | None = None
        self._follower: JournalFollower | None = None
        self._watcher: JournalWatcher | None = None
        self._notice: LocalDataNotice | None = None
        self._names: EngineeringNames | None = None
        self._catalogue_view: dict[str, Any] | None = None
        self._search: MiningSearch | None = None
        self._sources: dict[Source, CommunitySource] = {}
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
        layout_store = self._layout_store = LayoutStore(config)
        self._layout = layout_store.load()
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
                self._folders["recordings"], self._io.submit, self._clock.now(), build.version
            ),
            clock=self._clock,
            catalogue=catalogue,
            goals=SqliteGoalRepository(database, self._io.submit, self._core.submit, self._logger),
            ship_names=load_ship_names(),
        )
        names = self._names = EngineeringNames(catalogue, self._tl, companion.engineering.name_of)
        self._catalogue_view = catalogue_view(catalogue, EngineeringNames(catalogue, self._tl))
        self._presenter = ActivityPresenter(
            self._tl, self._format_number, companion.settings.display, names
        )
        self._search = self._mining_search(companion, database)
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
            self._folders,
        )

    def save_settings(self, request: Mapping[str, Any]) -> None:
        def save() -> None:
            companion = self._require_companion()
            try:
                settings, preferences = settings_from_request(request, companion.settings)
            except SettingsError as error:
                self._logger.warning("Settings refused: %s", error)
                return
            for source, turned_off in (
                (Source.SPANSH, companion.settings.sources.spansh and not settings.sources.spansh),
                (Source.ARDENT, companion.settings.sources.ardent and not settings.sources.ardent),
            ):
                if turned_off:
                    self._sources[source].clear()
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

    # Layout of the views (ADR 0021)

    def layout(self) -> dict[str, Any]:
        """The order of each view's cards, and those folded. The layout is replaced, never
        changed: any thread."""
        return layout_view(self._layout)

    def save_layout(self, view: str, request: Mapping[str, Any]) -> None:
        def save() -> None:
            try:
                changed = view_layout_from_request(view, request)
            except LayoutError as error:
                self._logger.warning("Layout refused: %s", error)
                return
            if changed == self._layout[view]:
                return
            self._layout = {**self._layout, view: changed}
            assert self._layout_store is not None, "created at start, with the companion"
            self._layout_store.save(self._layout)

        self._core.submit(save)

    def open_folder(self, name: str) -> None:
        """Show the folder of the journal recordings or of the logs, for a bug report."""
        folder = self._folders.get(name)
        if folder is None:
            self._logger.warning("Unknown folder to open: %r", name)
            return

        def show() -> None:
            try:
                folder.mkdir(parents=True, exist_ok=True)
                self._open_folder(folder)
            except OSError as error:
                self._logger.warning("Could not open %s: %s", folder, error)

        self._io.submit(show)

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
                goal = goal_from_request(
                    request,
                    engineering.catalogue,
                    engineering.equipment,
                    self._clock.now(),
                    engineering.engineers,
                )
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

    def order_goals(self, order: list[str]) -> None:
        """The player's priority (ADR 0033): the goals it names first, then the others."""

        def reorder() -> None:
            if not isinstance(order, list) or not all(isinstance(id_, str) for id_ in order):
                self._logger.warning("Goal order refused: %r", order)
                return
            engineering = self._require_companion().engineering
            self._apply(engineering.order_goals([GoalId(goal_id) for goal_id in order]))

        self._core.submit(reorder)

    # The Mining tab (ADR 0040): each call waits for the sources' answer, on the caller's thread

    def mining_options(self) -> dict[str, Any]:
        """What the tab's forms start from. Reads immutable objects only: any thread."""
        companion = self._require_companion()
        situation = companion.situation.situation
        pad = needed_pad(situation.ship.symbol) if situation.ship else None
        return options_view(situation.system, pad, companion.settings.sources, self._tl)

    def find_hotspots(self, request: Mapping[str, Any]) -> dict[str, Any]:
        try:
            query = hotspot_query(request)
        except ValueError as error:
            self._logger.warning("Hotspot search refused: %s", error)
            return refused("hotspots", "invalid")
        return self._wait(
            "hotspots",
            lambda done: self._require_search().find_hotspots(
                query,
                lambda answer: done(hotspots_view(answer, self._tl)),
                refresh=refresh(request),
            ),
        )

    def find_buyers(self, request: Mapping[str, Any]) -> dict[str, Any]:
        try:
            query = sale_query(request)
        except ValueError as error:
            self._logger.warning("Market search refused: %s", error)
            return refused("buyers", "invalid")
        return self._wait(
            "buyers",
            lambda done: self._require_search().find_buyers(
                query, lambda answer: done(buyers_view(answer)), refresh=refresh(request)
            ),
        )

    def estimate_cargo(self) -> dict[str, Any]:
        """The unsold cargo of the mining session, at the best market around the system."""

        def start(done: Callable[[dict[str, Any]], None]) -> None:
            companion = self._require_companion()
            situation = companion.situation.situation
            if situation.system is None:
                done(refused("estimate", "noSystem"))
                return
            stats = companion.mining.current_stats
            cargo = {c.key: tons for c, tons in (stats.unsold_tons if stats else {}).items()}
            if not cargo:
                done(refused("estimate", "empty"))
                return
            system = situation.system
            self._require_search().estimate_cargo(
                cargo,
                system,
                needed_pad(situation.ship.symbol) if situation.ship else None,
                lambda answer: done(estimate_view(answer, system, self._tl)),
            )

        return self._wait("estimate", start)

    def _wait(
        self, answer_kind: str, start: Callable[[Callable[[dict[str, Any]], None]], None]
    ) -> dict[str, Any]:
        """Run ``start`` on the core thread, and wait for the view it hands to ``done``; an empty
        ``answer_kind`` answer if it does not come in time."""
        answer: Future[dict[str, Any]] = Future()

        def job() -> None:
            try:
                start(answer.set_result)
            except Exception as error:
                answer.set_exception(error)

        self._core.submit(job)
        try:
            return answer.result(timeout=SEARCH_TIMEOUT)
        except TimeoutError:
            self._logger.warning("No answer from the sources in %.0f s", SEARCH_TIMEOUT)
            return refused(answer_kind, "down")

    def _mining_search(self, companion: Companion, database: LocalDatabase) -> MiningSearch:
        agent = user_agent(self.build)

        def source(name: Source, enabled: Callable[[], bool]) -> CommunitySource:
            return CommunitySource(
                name,
                database,
                enabled=enabled,
                submit=self._io.submit,
                dispatch=self._core.submit,
                now=self._clock.now,
                logger=self._logger,
            )

        spansh = source(Source.SPANSH, lambda: companion.settings.sources.spansh)
        ardent = source(Source.ARDENT, lambda: companion.settings.sources.ardent)
        self._sources = {Source.SPANSH: spansh, Source.ARDENT: ardent}
        return MiningSearch(
            SpanshCatalogue(spansh, SourceClient(agent, opener=self._http_opener), self._logger),
            ArdentMarkets(ardent, SourceClient(agent, opener=self._http_opener)),
            self._clock,
        )

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
            application_version=self.build.version,
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

    def _require_search(self) -> MiningSearch:
        if self._search is None:
            raise RuntimeError("the desktop core has not started")
        return self._search

    def _require_companion(self) -> Companion:
        if self._companion is None:
            raise RuntimeError("the desktop core has not started")
        return self._companion
