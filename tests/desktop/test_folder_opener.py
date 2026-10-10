"""Opening a folder in the platform's file manager."""

from pathlib import Path

import pytest

from edrockmaster.desktop.folder_opener import open_in_file_manager

FOLDER = Path("/data/logs")


def test_windows_opens_the_folder_in_the_explorer() -> None:
    opened: list[str] = []
    open_in_file_manager(FOLDER, "win32", startfile=opened.append, run=None)
    assert opened == [str(FOLDER)]


@pytest.mark.parametrize(("platform", "command"), [("darwin", "open"), ("linux", "xdg-open")])
def test_other_platforms_ask_their_opener(platform: str, command: str) -> None:
    runs: list[list[str]] = []
    open_in_file_manager(FOLDER, platform, startfile=None, run=runs.append)
    assert runs == [[command, str(FOLDER)]]
