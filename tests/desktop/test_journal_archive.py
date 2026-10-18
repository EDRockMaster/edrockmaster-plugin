import json
import logging
from pathlib import Path

import pytest

from edrockmaster.application.ports import JournalFile
from edrockmaster.desktop.journal_archive import FolderArchive

logger = logging.getLogger("test.journal_archive")
EVENTS = frozenset({"Bounty", "Shutdown"})


def write(folder: Path, name: str, *lines: str) -> Path:
    path = folder / name
    path.write_text("".join(f"{line}\r\n" for line in lines), encoding="utf-8")
    return path


def entry(event: str, **fields: object) -> str:
    return json.dumps({"timestamp": "2026-10-14T20:00:00Z", "event": event, **fields})


@pytest.fixture
def archive(tmp_path: Path) -> FolderArchive:
    return FolderArchive(tmp_path, logger)


def test_journal_files_oldest_first_betas_left_out(tmp_path: Path, archive: FolderArchive) -> None:
    write(tmp_path, "Journal.2026-10-15T190949.01.log", entry("Shutdown"))
    write(tmp_path, "Journal.2026-10-14T203648.01.log", entry("Fileheader"), entry("Shutdown"))
    write(tmp_path, "JournalBeta.2026-10-14T210000.01.log", entry("Shutdown"))
    write(tmp_path, "Status.json", "{}")
    files = archive.files()
    assert [file.name for file in files] == [
        "Journal.2026-10-14T203648.01.log",
        "Journal.2026-10-15T190949.01.log",
    ]
    assert files[0].size == (tmp_path / files[0].name).stat().st_size


def test_only_the_events_asked_for_are_given(tmp_path: Path, archive: FolderArchive) -> None:
    path = write(
        tmp_path,
        "Journal.2026-10-14T203648.01.log",
        entry("Fileheader", gameversion="4.4.1.1"),
        entry("Music", MusicTrack="Combat"),
        '{ "timestamp":"2026-10-14T20:01:00Z", "event":"Bounty", "TotalReward":1000 }',
        entry("Shutdown"),
    )
    found = list(archive.entries(JournalFile(path.name, 0), EVENTS))
    assert [e["event"] for e in found] == ["Bounty", "Shutdown"]
    assert found[0]["TotalReward"] == 1000


def test_lines_that_are_not_entries_are_skipped(tmp_path: Path, archive: FolderArchive) -> None:
    path = write(
        tmp_path,
        "Journal.2026-10-14T203648.01.log",
        '{ "event":"Bounty", "TotalReward": ',
        '"event":"Bounty"',
        '[{"event":"Bounty"}]',
        entry("Shutdown"),
    )
    path.write_bytes(path.read_bytes() + b'{"event":"Bounty", "x":"\xff"}\n')
    found = list(archive.entries(JournalFile(path.name, 0), EVENTS))
    assert [e["event"] for e in found] == ["Shutdown"]


def test_a_beta_of_the_game_gives_nothing(tmp_path: Path, archive: FolderArchive) -> None:
    path = write(
        tmp_path,
        "Journal.2026-10-14T203648.01.log",
        entry("Fileheader", gameversion="4.1.0.100 Beta"),
        entry("Bounty", TotalReward=1000),
    )
    assert list(archive.entries(JournalFile(path.name, 0), EVENTS)) == []


def test_a_file_gone_gives_nothing(
    archive: FolderArchive, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        assert (
            list(archive.entries(JournalFile("Journal.2026-10-14T203648.01.log", 0), EVENTS)) == []
        )
    assert "Could not read" in caplog.text


def test_a_missing_folder_has_no_files(tmp_path: Path) -> None:
    assert FolderArchive(tmp_path / "missing", logger).files() == []
