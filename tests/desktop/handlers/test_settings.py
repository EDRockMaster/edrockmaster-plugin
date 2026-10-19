"""The Settings page's calls, on a core context that runs each job at once (ADR 0041)."""

import logging
from pathlib import Path

import pytest

from edrockmaster.application.community import Source
from edrockmaster.application.updates import UpdateChannel
from edrockmaster.desktop.handlers.settings import SettingsHandler
from edrockmaster.desktop.settings_view import (
    DesktopPreferences,
    DesktopPreferencesStore,
    UpdateOffer,
)
from tests.desktop.handlers.fake_core import FakeCore
from tests.fakes import FakeConfig


class Settings:
    def __init__(self, tmp_path: Path, open_folder: object = None) -> None:
        self.core = FakeCore()
        self.config = FakeConfig()
        self.cleared: list[Source] = []
        self.languages: list[str] = []
        self.opened: list[Path] = []
        self.past_journals_read = 0
        self.update_checks = 0
        self.folders = {"recordings": tmp_path / "recordings", "logs": tmp_path / "logs"}
        self.handler = SettingsHandler(
            self.core.context,
            store=DesktopPreferencesStore(self.config),
            preferences=DesktopPreferences(),
            journal_folder=tmp_path / "journal",
            folders=self.folders,
            open_folder=open_folder or self.opened.append,  # type: ignore[arg-type]
            clear_source=self.cleared.append,
            set_language=self.languages.append,
            read_past_journals=self.read_again,
            update_offer=UpdateOffer(installed=True, default=UpdateChannel.STABLE),
            updates_changed=self.check_updates,
        )

    def check_updates(self) -> None:
        self.update_checks += 1

    def read_again(self) -> None:
        self.past_journals_read += 1


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(tmp_path)


def test_settings_saved_apply_and_are_kept(settings: Settings) -> None:
    request = settings.handler.settings()
    assert request["language"] == "auto"
    request.update(activities=["engineering"], language="fr", sound=False)
    settings.handler.save_settings(request)
    assert settings.core.companion.settings.sound_enabled is False
    assert settings.languages == ["fr"]
    assert settings.config.get_str("edrockmaster.desktop.language") == "fr"
    assert settings.handler.settings()["language"] == "fr"
    assert settings.core.refreshes == 1


def test_invalid_settings_are_logged_and_change_nothing(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    request = settings.handler.settings()
    with caplog.at_level(logging.WARNING):
        settings.handler.save_settings({**request, "language": "de", "sound": False})
    assert "Settings refused: language" in caplog.text
    assert settings.core.companion.settings.sound_enabled is True
    assert settings.core.refreshes == 0


def test_a_source_turned_off_forgets_its_answers(settings: Settings) -> None:
    request = settings.handler.settings()
    settings.handler.save_settings({**request, "sources": {"spansh": False, "ardent": True}})
    settings.handler.save_settings({**request, "sources": {"spansh": False, "ardent": False}})
    settings.handler.save_settings({**request, "sources": {"spansh": True, "ardent": True}})
    assert settings.cleared == [Source.SPANSH, Source.ARDENT]


def test_the_journal_folder_is_used_from_the_next_start(
    settings: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    request = settings.handler.settings()
    assert request["journalFolderInUse"] == str(tmp_path / "journal")
    with caplog.at_level(logging.INFO):
        settings.handler.save_settings({**request, "journalFolder": str(tmp_path / "other")})
    assert "used from the next start" in caplog.text
    assert settings.handler.settings()["journalFolderInUse"] == str(tmp_path / "journal")


def test_the_recordings_and_logs_folders_open(settings: Settings, tmp_path: Path) -> None:
    shown = settings.handler.settings()
    assert shown["recordingsFolder"] == str(tmp_path / "recordings")
    assert shown["logsFolder"] == str(tmp_path / "logs")
    settings.handler.open_folder("recordings")
    settings.handler.open_folder("logs")
    assert settings.opened == [tmp_path / "recordings", tmp_path / "logs"]
    # Before the first recording, its folder does not exist yet: it is made to be opened
    assert (tmp_path / "recordings").is_dir()


def test_only_the_application_s_folders_open(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(folder: Path) -> None:
        raise OSError("no file manager")

    settings = Settings(tmp_path, broken)
    with caplog.at_level(logging.WARNING):
        settings.handler.open_folder("C:/Windows")
        settings.handler.open_folder("logs")
    assert "Unknown folder to open: 'C:/Windows'" in caplog.text
    assert "Could not open" in caplog.text
    assert "no file manager" in caplog.text


def test_past_journals_are_read_again_when_asked(settings: Settings) -> None:
    settings.handler.read_past_journals()
    assert settings.past_journals_read == 1


def test_update_settings_changed_check_again(settings: Settings) -> None:
    assert settings.handler.update_wish() == (True, None)
    request = settings.handler.settings()
    request["language"] = "fr"
    settings.handler.save_settings(request)
    assert settings.update_checks == 0  # the language only
    request["updates"]["channel"] = "beta"
    settings.handler.save_settings(request)
    assert settings.update_checks == 1
    assert settings.handler.update_wish() == (True, UpdateChannel.BETA)
    assert settings.config.get_str("edrockmaster.desktop.update_channel") == "beta"
