"""The desktop application without its window (ADR 0020): journal, core, storage.

``DesktopCore`` is the composition root of the application. It builds the core
(the ``Companion`` of the activities, the local database, the goals, the
catalogue), feeds it with the journal reader, and pushes the live view to the
interface after each change. The interface's calls go to a handler per context
(``desktop/handlers/``, ADR 0041), which reaches the core through a ``CoreContext``.

Threads: every call to the companion and to the presenter happens on the
**core thread**, fed by a queue: the journal reader's thread and the
interface's calls only submit jobs to it. The I/O thread of ADR 0018 does the
disk work. ``push`` is called on the core thread and must not block. The
journals of past game sessions are read on a thread of their own (ADR 0052),
at start and each time the game opens a new file, without holding the live view.
An application installed by Velopack looks for its updates on a thread of its own
too (ADR 0053).
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from edrockmaster import VERSION
from edrockmaster.application.activity import Activity
from edrockmaster.application.build import BuildInfo
from edrockmaster.application.community import Source
from edrockmaster.application.companion import Companion, Notification
from edrockmaster.application.market_search import MarketSearch
from edrockmaster.application.mining_search import MiningSearch
from edrockmaster.application.past_journals import PastJournalReader, PastJournalsRead
from edrockmaster.application.ports import Clock, UpdateSource
from edrockmaster.application.updates import UpdateReady, UpdateService, default_channel
from edrockmaster.desktop.engineering_view import engineering_view
from edrockmaster.desktop.folder_opener import open_in_file_manager
from edrockmaster.desktop.handlers.context import CoreContext
from edrockmaster.desktop.handlers.engineering import EngineeringHandler
from edrockmaster.desktop.handlers.layout import LayoutHandler
from edrockmaster.desktop.handlers.mining import MiningHandler
from edrockmaster.desktop.handlers.phone import PhoneHandler
from edrockmaster.desktop.handlers.settings import SettingsHandler
from edrockmaster.desktop.handlers.trade import TradeHandler
from edrockmaster.desktop.journal_archive import FolderArchive
from edrockmaster.desktop.journal_folder import default_journal_folder
from edrockmaster.desktop.journal_reader import POLL_SECONDS, JournalFollower, JournalWatcher
from edrockmaster.desktop.layout import LayoutStore
from edrockmaster.desktop.live_view import live_view
from edrockmaster.desktop.phone import Phone, PhoneStore
from edrockmaster.desktop.settings_view import DesktopPreferencesStore, UpdateOffer
from edrockmaster.desktop.updates import Updates
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.situation.route import JumpDiverted
from edrockmaster.infrastructure.build_file import load_build
from edrockmaster.infrastructure.catalogue_file import load_catalogue
from edrockmaster.infrastructure.clock import SystemClock
from edrockmaster.infrastructure.commodity_catalogue_file import load_commodities
from edrockmaster.infrastructure.database import FILE_NAME as DATABASE_FILE_NAME
from edrockmaster.infrastructure.database import LocalDatabase, Opening
from edrockmaster.infrastructure.goal_repository import SqliteGoalRepository
from edrockmaster.infrastructure.past_journal_store import SqlitePastJournalStore
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
from edrockmaster.infrastructure.velopack_updates import VelopackUpdates
from edrockmaster.infrastructure.worker import IoWorker
from edrockmaster.ui.engineering_names import EngineeringNames
from edrockmaster.ui.panel_model import LocalDataNotice
from edrockmaster.ui.presenter import ActivityPresenter

if sys.platform == "win32":  # pragma: no cover
    import winsound

CORE_THREAD = "EDRockMaster core"
PAST_JOURNALS_THREAD = "EDRockMaster past journals"
RECORDINGS_DIRECTORY = "recordings"
PACKAGE_DIRECTORY = Path(__file__).resolve().parents[1]

type Push = Callable[[dict[str, Any]], None]
"""Sends the live view to the interface; called on the core thread, must not block."""


def game_description(entry: Entry, is_beta: bool = False) -> str:
    """The game a ``LoadGame`` entry tells of, for the log: a bug report then says which."""
    version = entry.get("gameversion")
    build = entry.get("build")
    parts = [f"Elite Dangerous {version}" if isinstance(version, str) else "Elite Dangerous"]
    if not isinstance(version, str):
        parts[0] += ", version unknown"
    elif isinstance(build, str) and build.strip():
        parts[0] += f" (build {build.strip()})"
    if entry.get("Odyssey") is True:
        parts.append("Odyssey")
    elif entry.get("Horizons") is True:
        parts.append("Horizons")
    if is_beta:
        parts.append("beta")
    return ", ".join(parts)


@dataclass(frozen=True)
class Handlers:
    """The interface's calls, by context (ADR 0041)."""

    settings: SettingsHandler
    layout: LayoutHandler
    engineering: EngineeringHandler
    mining: MiningHandler
    trade: TradeHandler
    phone: PhoneHandler


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
        update_source: Callable[[], UpdateSource | None] = lambda: VelopackUpdates.installed(
            os.environ
        ),
        phone: Phone | None = None,
    ) -> None:
        """``journal_folder``: set by the environment, before the settings' and the usual one;
        ``language``: the system's, unless the settings choose another; ``logs_directory``:
        where the log file is, in the data directory unless the demo keeps its data apart;
        ``update_source``: the installation's updates, ``None`` if not installed to update;
        ``phone``: the local server for a phone or a tablet (ADR 0055), the window's own."""
        self._data = data_directory
        self._folders = {
            "recordings": data_directory / RECORDINGS_DIRECTORY,
            "logs": logs_directory or data_directory / "logs",
        }
        self._open_folder = open_folder
        self._http_opener = http_opener
        self._update_source = update_source
        self._phone = phone or Phone(
            lambda name, arguments: None, lambda: "", logger, addresses=list
        )
        self._updates: Updates | None = None
        self._update: UpdateReady | None = None
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
        self._past_journals = IoWorker(logger, PAST_JOURNALS_THREAD)
        self._past_reader: PastJournalReader | None = None
        self._translations = translator(language)
        self._number_format = number_format(language)
        self._presenter = ActivityPresenter(self._tl, self._format_number)
        self._handlers: Handlers | None = None
        self._companion: Companion | None = None
        self._database: LocalDatabase | None = None
        self._follower: JournalFollower | None = None
        self._watcher: JournalWatcher | None = None
        self._notice: LocalDataNotice | None = None
        self._names: EngineeringNames | None = None
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

    @property
    def handlers(self) -> Handlers:
        """The interface's calls, once started."""
        if self._handlers is None:
            raise RuntimeError("the desktop core has not started")
        return self._handlers

    def start(self) -> None:
        build = self.build
        config = JsonFileConfig(self._data / SETTINGS_FILE_NAME, self._io.submit, self._logger)
        store = DesktopPreferencesStore(config)
        preferences = store.load()
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
        self._presenter = ActivityPresenter(
            self._tl, self._format_number, companion.settings.display, names
        )
        sources = self._sources(companion, database)
        markets = self._markets(sources)
        update_source = self._update_source()
        default = default_channel(build.channel)
        context = CoreContext(
            on_core=self._core.submit,
            on_io=self._io.submit,
            companion=self._require_companion,
            apply=self._apply,
            refresh=self._send,
            tl=self._tl,
            language=lambda: self._language,
            clock=self._clock,
            logger=self._logger,
        )
        self._handlers = Handlers(
            settings=SettingsHandler(
                context,
                store=store,
                preferences=preferences,
                journal_folder=self._journal_folder,
                folders=self._folders,
                open_folder=self._open_folder,
                clear_source=lambda source: sources[source].clear(),
                set_language=self._set_language,
                read_past_journals=self._read_past_journals_again,
                update_offer=UpdateOffer(installed=update_source is not None, default=default),
                updates_changed=self._check_updates,
            ),
            layout=LayoutHandler(context, LayoutStore(config)),
            engineering=EngineeringHandler(context),
            mining=MiningHandler(context, MiningSearch(self._galaxy(sources))),
            trade=TradeHandler(context, load_commodities(), markets),
            phone=PhoneHandler(context, store=PhoneStore(config), phone=self._phone),
        )
        self._handlers.phone.start()
        companion.engineering.load_goals(self._apply)
        if update_source is None:
            self._logger.info("Not installed to update itself: no updates")
        else:
            self._updates = Updates(
                UpdateService(update_source, default),
                self._handlers.settings.update_wish,
                self._on_update_ready,
                self._logger,
            )
            self._updates.start()
        if self._journal_folder is not None:
            self._past_reader = PastJournalReader(
                FolderArchive(self._journal_folder, self._logger),
                SqlitePastJournalStore(database, self._io, self._logger),
                self._on_past_journals,
            )
            self._past_journals.start()
            follower = self._follower = JournalFollower(
                self._journal_folder, self._on_entry, self._logger, on_file=self._on_journal_file
            )
            self._watcher = JournalWatcher(follower, self._logger, self._poll_interval)
            self._watcher.start()
        else:
            self._logger.warning("No journal folder found: nothing to read")

    def stop(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
        # A first reading of years of journals may still run: it starts again next time
        self._past_journals.stop(timeout=1.0)
        self._core.stop()
        if self._database is not None:
            self._io.submit(self._database.close)
        self._io.stop()
        self._phone.stop()
        if self._updates is not None:
            self._updates.stop()
            self._updates.at_exit()
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

    def restart_to_update(self) -> bool:
        """The player restarts to update: ``True`` if the window is to close, the version ready
        then applied and the application started again."""
        return self._updates is not None and self._updates.restart()

    # Updates (ADR 0053)

    def _check_updates(self) -> None:
        if self._updates is not None:
            self._updates.check_now()

    def _on_update_ready(self, ready: UpdateReady) -> None:
        """From the updates thread: queued for the core thread."""

        def show() -> None:
            self._update = ready
            self._send()

        self._core.submit(show)

    def _sources(
        self, companion: Companion, database: LocalDatabase
    ) -> dict[Source, CommunitySource]:
        """The community sources (ADR 0039), each on when the player's settings say so."""

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

        return {
            Source.SPANSH: source(Source.SPANSH, lambda: companion.settings.sources.spansh),
            Source.ARDENT: source(Source.ARDENT, lambda: companion.settings.sources.ardent),
        }

    def _galaxy(self, sources: dict[Source, CommunitySource]) -> SpanshCatalogue:
        return SpanshCatalogue(
            sources[Source.SPANSH],
            SourceClient(user_agent(self.build), opener=self._http_opener),
            self._logger,
        )

    def _markets(self, sources: dict[Source, CommunitySource]) -> MarketSearch:
        """Where to buy and sell, for the Mining and Trade tabs."""
        client = SourceClient(user_agent(self.build), opener=self._http_opener)
        return MarketSearch(ArdentMarkets(sources[Source.ARDENT], client), self._clock)

    # The journals of past game sessions (ADR 0052)

    def _on_journal_file(self, path: Path) -> None:
        """From the journal reader's thread: a file opened, the one before may now be complete."""
        self._core.submit(lambda: self._require_companion().combat.journal_file_opened(path.name))
        self._past_journals.submit(self._catch_up)

    def _read_past_journals_again(self) -> None:
        """The player asked: forget what the past journals gave, and read them all again."""
        self._logger.info("Reading the past journals again, as asked")
        self._past_journals.submit(self._read_again)

    def _catch_up(self) -> None:
        if self._past_reader is not None:
            self._past_reader.catch_up()

    def _read_again(self) -> None:
        if self._past_reader is not None:
            self._past_reader.read_again()

    def _on_past_journals(self, read: PastJournalsRead) -> None:
        """From the past journals' thread: queued for the core thread."""

        def apply() -> None:
            if read.past.complete:
                self._logger.info("Past journals: %d files counted", len(read.indexed))
            self._apply(self._require_companion().combat.past_journals_read(read))

        self._core.submit(apply)

    # The core thread

    def _on_entry(self, entry: Entry, is_beta: bool) -> None:
        """From the journal reader's thread: queued for the core thread."""
        self._core.submit(lambda: self._handle(entry, is_beta))

    def _handle(self, entry: Entry, is_beta: bool) -> None:
        if entry.get("event") == "LoadGame":
            self._logger.info("Game loaded: %s", game_description(entry, is_beta))
        try:
            notifications = self._require_companion().handle_journal_entry(entry, is_beta)
        except Exception:
            self._logger.exception("Could not handle the journal entry %r", entry.get("event"))
            return
        for diverted in notifications:
            if isinstance(diverted, JumpDiverted):
                # Kept to survey what the game wrote, a Thargoid hyperdiction for one (ADR 0043)
                self._logger.info(
                    "Jump to %s at %s ended %s%s",
                    diverted.aimed,
                    diverted.at.isoformat(),
                    f"in {diverted.reached}" if diverted.reached else "before any arrival",
                    ", back where it left: a Thargoid hyperdiction?" if diverted.back else "",
                )
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
        if not self._interface_ready:
            return
        view = live_view(
            language=self._language,
            current=self._presenter.current.value,
            blocks=self._presenter.blocks_of(companion.settings.display.activities),
            notice=self._notice,
            update=self._update,
            journal_folder=self._journal_folder,
            journal_file=self._follower.current_file if self._follower else None,
            situation=companion.situation.situation,
            engineering=engineering_view(companion.engineering, self._require_names()),
            station_market=companion.trade.station_market,
        )
        try:
            self._push(view)
        except Exception:
            self._logger.exception("Could not send the live view to the interface")
        self._phone.publish(view)

    # Language: the presenters translate through these, so that a change applies at once

    def _tl(self, text: str) -> str:
        return self._translations(text)

    def _format_number(self, number: float, decimals: int) -> str:
        return self._number_format(number, decimals)

    def _set_language(self, choice: str) -> None:
        language = self._system_language if choice == "auto" else choice
        if language == self._language:
            return
        self._language = language
        self._translations = translator(language)
        self._number_format = number_format(language)

    def _require_names(self) -> EngineeringNames:
        if self._names is None:
            raise RuntimeError("the desktop core has not started")
        return self._names

    def _require_companion(self) -> Companion:
        if self._companion is None:
            raise RuntimeError("the desktop core has not started")
        return self._companion
