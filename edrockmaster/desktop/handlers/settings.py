"""The Settings page's calls (ADR 0020): the settings, the application's folders, reading
the journals of past game sessions again (ADR 0052), and the updates (ADR 0053)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from edrockmaster.application.community import Source
from edrockmaster.application.updates import UpdateChannel
from edrockmaster.desktop.handlers.context import CoreContext
from edrockmaster.desktop.settings_view import (
    DesktopPreferences,
    DesktopPreferencesStore,
    SettingsError,
    UpdateOffer,
    settings_from_request,
    settings_view,
)


class SettingsHandler:
    def __init__(  # noqa: PLR0913 - what the page shows and what a change reaches
        self,
        context: CoreContext,
        *,
        store: DesktopPreferencesStore,
        preferences: DesktopPreferences,
        journal_folder: Path | None,
        folders: Mapping[str, Path],
        open_folder: Callable[[Path], None],
        clear_source: Callable[[Source], None],
        set_language: Callable[[str], None],
        read_past_journals: Callable[[], None],
        update_offer: UpdateOffer,
        updates_changed: Callable[[], None],
    ) -> None:
        """``journal_folder``: the one in use since the start; ``folders``: those the page may
        open, by name; ``clear_source``: forgets what a source answered, once turned off;
        ``set_language``: applies the language chosen, on the core thread;
        ``read_past_journals``: forgets what the past journals gave and reads them again;
        ``update_offer``: whether the application updates itself, and its build's channel;
        ``updates_changed``: checks again, the update settings changed."""
        self._context = context
        self._store = store
        self._preferences = preferences
        self._journal_folder = journal_folder
        self._folders = folders
        self._open_folder = open_folder
        self._clear_source = clear_source
        self._set_language = set_language
        self.read_past_journals = read_past_journals
        """Does not block: the past journals are read on a thread of their own."""
        self._update_offer = update_offer
        self._updates_changed = updates_changed

    def update_wish(self) -> tuple[bool, UpdateChannel | None]:
        """Whether to check for updates, and the channel chosen. Reads an immutable object:
        any thread."""
        preferences = self._preferences
        return preferences.check_updates, preferences.update_channel

    def settings(self) -> dict[str, Any]:
        """What the settings form shows. Reads immutable objects only: any thread."""
        return settings_view(
            self._context.companion().settings,
            self._preferences,
            self._journal_folder,
            self._context.tl,
            self._folders,
            updates=self._update_offer,
        )

    def save_settings(self, request: Mapping[str, Any]) -> None:
        def save() -> None:
            companion = self._context.companion()
            try:
                settings, preferences = settings_from_request(
                    request, companion.settings, self._update_offer.default
                )
            except SettingsError as error:
                self._context.logger.warning("Settings refused: %s", error)
                return
            for source, turned_off in (
                (Source.SPANSH, companion.settings.sources.spansh and not settings.sources.spansh),
                (Source.ARDENT, companion.settings.sources.ardent and not settings.sources.ardent),
            ):
                if turned_off:
                    self._clear_source(source)
            companion.change_settings(settings)
            if preferences != self._preferences:
                self._store.save(preferences)
                if preferences.journal_folder != self._preferences.journal_folder:
                    self._context.logger.info("Journal folder set, used from the next start")
                updates_changed = self.update_wish() != (
                    preferences.check_updates,
                    preferences.update_channel,
                )
                self._preferences = preferences
                self._set_language(preferences.language)
                if updates_changed:
                    self._updates_changed()
            self._context.refresh()

        self._context.on_core(save)

    def open_folder(self, name: str) -> None:
        """Show the folder of the journal recordings or of the logs, for a bug report."""
        folder = self._folders.get(name)
        if folder is None:
            self._context.logger.warning("Unknown folder to open: %r", name)
            return

        def show() -> None:
            try:
                folder.mkdir(parents=True, exist_ok=True)
                self._open_folder(folder)
            except OSError as error:
                self._context.logger.warning("Could not open %s: %s", folder, error)

        self._context.on_io(show)
