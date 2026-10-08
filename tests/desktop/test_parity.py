"""The desktop application's journal reader hands the core what EDMC handed the plugin (ADR 0020).

Each fixture is a recording of what EDMC handed the plugin, live, from before the
game started. Written back as the game writes its journal, and read by the
journal reader, it must give the core the same entries, hence the same figures.
"""

import json
import logging
from pathlib import Path

import pytest

from edrockmaster.desktop.journal_reader import JournalFollower
from tests.test_replay import FIXTURES, Replay, records

FIXTURE_NAMES = sorted(path.name for path in FIXTURES.glob("*.jsonl"))
logger = logging.getLogger("test.parity")


def write_journal(directory: Path, fixture: str, chunk: int) -> list[Path]:
    """The fixture as journal files of ``chunk`` entries: the game splits long sessions."""
    entries = [record["entry"] for record in records(fixture)]
    files = []
    for part, start in enumerate(range(0, len(entries), chunk), 1):
        path = directory / f"Journal.2026-10-08T014139.{part:02d}.log"
        lines = (
            json.dumps(entry, ensure_ascii=False) + "\r\n"
            for entry in entries[start : start + chunk]
        )
        path.write_text("".join(lines), encoding="utf-8", newline="")
        files.append(path)
    return files


@pytest.mark.parametrize("fixture", FIXTURE_NAMES)
def test_reading_the_journal_gives_the_plugin_s_figures(fixture: str, tmp_path: Path) -> None:
    through_edmc = Replay(fixture)
    write_journal(tmp_path, fixture, chunk=10_000)
    through_reader = Replay(None)
    JournalFollower(tmp_path, through_reader.handle, logger).poll()
    assert through_reader.notifications == through_edmc.notifications
    assert through_reader.panel_switches == through_edmc.panel_switches


def test_a_session_split_in_parts_read_as_the_game_writes_them(tmp_path: Path) -> None:
    fixture = "engineering-power-distributor-2026-10-08.jsonl"
    through_edmc = Replay(fixture)
    files = write_journal(tmp_path, fixture, chunk=100)
    assert len(files) > 2
    # The reader starts while only the first part exists, then the game writes the others
    staged = tmp_path / "staged"
    staged.mkdir()
    for path in files[1:]:
        path.rename(staged / path.name)
    through_reader = Replay(None)
    follower = JournalFollower(tmp_path, through_reader.handle, logger)
    follower.poll()
    for path in files[1:]:
        (staged / path.name).rename(path)
        follower.poll()
    assert through_reader.notifications == through_edmc.notifications
    assert through_reader.companion.engineering.inventory == (
        through_edmc.companion.engineering.inventory
    )


def test_fixtures_are_found() -> None:
    assert "engineering-power-distributor-2026-10-08.jsonl" in FIXTURE_NAMES
