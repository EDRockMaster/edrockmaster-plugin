from pathlib import Path

import pytest

from edrockmaster.desktop.journal_folder import (
    GAME_FOLDER,
    default_journal_folder,
    environment_override,
    is_beta_file,
    journal_files,
    newest_journal,
)


def touch(directory: Path, *names: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_text("")


def test_journal_files_are_ordered_by_their_start_then_part(tmp_path: Path) -> None:
    touch(
        tmp_path,
        "Journal.2026-10-08T014139.02.log",
        "Journal.2026-10-08T014139.01.log",
        "Journal.220315152335.01.log",  # the format before 2022
        "Journal.2026-10-07T220000.01.log",
        "Status.json",
        "Journal.2026-13-40T999999.01.log",  # not a date
        "journal.txt",
    )
    assert [path.name for path in journal_files(tmp_path)] == [
        "Journal.220315152335.01.log",
        "Journal.2026-10-07T220000.01.log",
        "Journal.2026-10-08T014139.01.log",
        "Journal.2026-10-08T014139.02.log",
    ]
    newest = newest_journal(tmp_path)
    assert newest is not None
    assert newest.name == "Journal.2026-10-08T014139.02.log"


def test_no_journal_file(tmp_path: Path) -> None:
    assert newest_journal(tmp_path) is None
    assert journal_files(tmp_path / "missing") == []


def test_beta_files() -> None:
    assert is_beta_file(Path("JournalBeta.2026-10-08T014139.01.log"))
    assert not is_beta_file(Path("Journal.2026-10-08T014139.01.log"))


def test_windows_saved_games_known_folder_first(tmp_path: Path) -> None:
    moved = tmp_path / "D" / "Games"
    (moved / GAME_FOLDER).mkdir(parents=True)
    (tmp_path / "home" / "Saved Games" / GAME_FOLDER).mkdir(parents=True)
    found = default_journal_folder("win32", tmp_path / "home", lambda: moved)
    assert found == moved / GAME_FOLDER
    # The known folder unknown or empty: the usual place in the profile
    usual = tmp_path / "home" / "Saved Games" / GAME_FOLDER
    assert default_journal_folder("win32", tmp_path / "home", lambda: None) == usual


@pytest.mark.parametrize(
    "steam",
    [".steam/steam", ".local/share/Steam", ".var/app/com.valvesoftware.Steam/.local/share/Steam"],
)
def test_linux_proton_prefix(tmp_path: Path, steam: str) -> None:
    folder = (
        tmp_path
        / steam
        / "steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games"
        / GAME_FOLDER
    )
    folder.mkdir(parents=True)
    assert default_journal_folder("linux", tmp_path) == folder


def test_no_journal_folder(tmp_path: Path) -> None:
    assert default_journal_folder("linux", tmp_path) is None


def test_a_folder_set_by_hand() -> None:
    assert environment_override({"EDROCKMASTER_JOURNAL_DIR": "/games/journal"}) == Path(
        "/games/journal"
    )
    assert environment_override({}) is None
