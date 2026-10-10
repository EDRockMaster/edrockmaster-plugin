import json
import logging
import threading
from pathlib import Path
from typing import Any

import pytest

from edrockmaster.desktop.journal_reader import JournalFollower, JournalWatcher
from edrockmaster.domain.journal_reading import Entry

logger = logging.getLogger("test.journal_reader")
FIRST = "Journal.2026-10-08T014139.01.log"
SECOND = "Journal.2026-10-08T014139.02.log"


def line(event: str, **fields: object) -> str:
    return json.dumps({"timestamp": "2026-10-08T01:42:20Z", "event": event, **fields}) + "\r\n"


class Journal:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        directory.mkdir(exist_ok=True)
        self.received: list[tuple[str, bool]] = []
        self.follower = JournalFollower(directory, self.receive, logger)

    def receive(self, entry: Entry, is_beta: bool) -> None:
        self.received.append((str(entry["event"]), is_beta))

    def write(self, name: str, text: str) -> None:
        with (self.directory / name).open("a", encoding="utf-8", newline="") as file:
            file.write(text)

    def events(self) -> list[str]:
        return [event for event, _ in self.received]


@pytest.fixture
def journal(tmp_path: Path) -> Journal:
    return Journal(tmp_path / "journal")


def test_at_start_the_current_file_is_read_from_its_beginning(journal: Journal) -> None:
    journal.write("Journal.2026-10-07T220000.01.log", line("Old"))
    journal.write(FIRST, line("Fileheader", gameversion="4.4.1.1") + line("Materials"))
    assert journal.follower.poll() == 2
    assert journal.events() == ["Fileheader", "Materials"]
    assert journal.follower.current_file == journal.directory / FIRST


def test_then_only_what_the_game_adds(journal: Journal) -> None:
    journal.write(FIRST, line("LoadGame"))
    journal.follower.poll()
    assert journal.follower.poll() == 0
    journal.write(FIRST, line("Music") + line("Shutdown"))
    assert journal.follower.poll() == 2
    assert journal.events() == ["LoadGame", "Music", "Shutdown"]


def test_an_incomplete_line_waits_for_the_rest(journal: Journal) -> None:
    whole = line("MaterialCollected", Name="iron", Count=3)
    journal.write(FIRST, whole[:20])
    assert journal.follower.poll() == 0
    journal.write(FIRST, whole[20:])
    assert journal.follower.poll() == 1
    assert journal.events() == ["MaterialCollected"]


def test_the_current_file_is_finished_before_the_next_part(journal: Journal) -> None:
    journal.write(FIRST, line("LoadGame"))
    journal.follower.poll()
    # Between two polls, the game ends a part and starts the next one
    journal.write(FIRST, line("Continue", Part=2))
    journal.write(SECOND, line("Fileheader", part=2) + line("Music"))
    assert journal.follower.poll() == 3
    assert journal.events() == ["LoadGame", "Continue", "Fileheader", "Music"]
    assert journal.follower.current_file == journal.directory / SECOND


def test_a_current_file_moved_away_gives_way_to_the_newest(journal: Journal) -> None:
    journal.write(FIRST, line("LoadGame"))
    journal.follower.poll()
    (journal.directory / FIRST).unlink()
    journal.write(SECOND, line("Music"))
    journal.follower.poll()
    assert journal.events() == ["LoadGame", "Music"]


def test_entries_of_a_beta_say_so(journal: Journal) -> None:
    journal.write("JournalBeta.2026-10-08T014139.01.log", line("Fileheader", gameversion="4.5"))
    journal.follower.poll()
    journal.write(SECOND, line("Fileheader", gameversion="4.5.0.100 Beta") + line("Music"))
    journal.follower.poll()
    journal.write(
        "Journal.2026-10-09T010000.01.log",
        line("Fileheader", gameversion="4.4.1.1") + line("Music"),
    )
    journal.follower.poll()
    assert journal.received == [
        ("Fileheader", True),
        ("Fileheader", True),
        ("Music", True),
        ("Fileheader", False),
        ("Music", False),
    ]


def test_lines_that_are_not_entries_are_logged_and_skipped(
    journal: Journal, caplog: pytest.LogCaptureFixture
) -> None:
    journal.write(FIRST, "{not json\r\n" + "[1, 2]\r\n" + "\r\n" + line("Music"))
    with caplog.at_level(logging.WARNING):
        assert journal.follower.poll() == 1
    assert caplog.text.count("Not a journal entry") == 2


def test_no_journal_yet_is_logged_once(journal: Journal, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert journal.follower.poll() == 0
        assert journal.follower.poll() == 0
    assert caplog.text.count("No journal file") == 1
    journal.write(FIRST, line("Music"))
    assert journal.follower.poll() == 1


def test_an_unreadable_file_is_logged(
    journal: Journal, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal.write(FIRST, line("Music"))

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("locked")

    monkeypatch.setattr(Path, "open", refuse)
    with caplog.at_level(logging.WARNING):
        assert journal.follower.poll() == 0
    assert "locked" in caplog.text


CARGO_AT = "2026-10-08T01:42:20Z"
INVENTORY = [{"Name": "painite", "Name_Localised": "Painite", "Count": 12, "Stolen": 0}]


def cargo_file(journal: Journal, timestamp: str = CARGO_AT, vessel: str = "Ship") -> None:
    content = {"timestamp": timestamp, "event": "Cargo", "Vessel": vessel, "Count": 12}
    (journal.directory / "Cargo.json").write_text(
        json.dumps({**content, "Inventory": INVENTORY}), encoding="utf-8"
    )


def test_the_ship_s_cargo_comes_from_cargo_json_as_edmc_added_it(tmp_path: Path) -> None:
    handed: list[Entry] = []
    follower = JournalFollower(tmp_path, lambda entry, _beta: handed.append(entry), logger)
    journal = Journal(tmp_path)
    cargo_file(journal)
    # Since 3.3, the journal's Cargo event lists the cargo only at load: the rest is in Cargo.json
    journal.write(FIRST, line("Cargo", Vessel="Ship", Count=12))
    follower.poll()
    assert handed[0]["Inventory"] == INVENTORY
    assert handed[0]["Count"] == 12


@pytest.mark.parametrize("before", ["older", "half-written"])
def test_the_game_may_write_cargo_json_just_after_the_line(tmp_path: Path, before: str) -> None:
    handed: list[Entry] = []
    waits: list[float] = []
    journal = Journal(tmp_path)
    # Seen in the game: Cargo.json written 22 ms after its journal line
    if before == "older":
        cargo_file(journal, timestamp="2026-10-08T01:00:00Z")
    else:
        (tmp_path / "Cargo.json").write_text('{"timestamp": "2026-10-08T01:4', encoding="utf-8")

    def wait(seconds: float) -> None:
        waits.append(seconds)
        if len(waits) == 2:
            cargo_file(journal)

    follower = JournalFollower(
        tmp_path, lambda entry, _beta: handed.append(entry), logger, sleep=wait
    )
    journal.write(FIRST, line("Cargo", Vessel="Ship", Count=12))
    follower.poll()
    assert handed[0]["Inventory"] == INVENTORY
    assert len(waits) == 2


def test_a_cargo_json_held_by_the_game_is_read_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handed: list[Entry] = []
    journal = Journal(tmp_path)
    cargo_file(journal)
    read_text = Path.read_text
    refusals = iter([PermissionError("held")])

    def held_once(path: Path, *args: Any, **kwargs: Any) -> str:
        for refusal in refusals:
            raise refusal
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", held_once)
    follower = JournalFollower(
        tmp_path, lambda entry, _beta: handed.append(entry), logger, sleep=lambda _s: None
    )
    journal.write(FIRST, line("Cargo", Vessel="Ship", Count=12))
    follower.poll()
    assert handed[0]["Inventory"] == INVENTORY


@pytest.mark.parametrize("left", ["older", "invalid"])
def test_a_cargo_json_that_never_comes_is_waited_for_a_moment_only(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, left: str
) -> None:
    handed: list[Entry] = []
    waits: list[float] = []
    journal = Journal(tmp_path)
    if left == "older":
        cargo_file(journal, timestamp="2026-10-08T01:00:00Z")
    else:
        (tmp_path / "Cargo.json").write_text("[1, 2", encoding="utf-8")
    follower = JournalFollower(
        tmp_path, lambda entry, _beta: handed.append(entry), logger, sleep=waits.append
    )
    journal.write(FIRST, line("Cargo", Vessel="Ship", Count=12))
    with caplog.at_level(logging.WARNING):
        follower.poll()
    assert "Inventory" not in handed[0]
    assert waits == [0.05] * 20
    assert "Cargo.json" in caplog.text


@pytest.mark.parametrize(
    ("event", "cargo"),
    [
        # An older event, read at start: Cargo.json describes a later one
        (line("Cargo", Vessel="Ship", Count=3).replace(CARGO_AT, "2026-10-08T01:00:00Z"), "ship"),
        # The SRV's cargo is not the ship's
        (line("Cargo", Vessel="SRV", Count=2), "srv"),
        # The event already lists it: the file is not needed
        (line("Cargo", Vessel="Ship", Count=1, Inventory=[]), "ship"),
        # No file
        (line("Cargo", Vessel="Ship", Count=12), "missing"),
    ],
)
def test_otherwise_the_cargo_event_is_left_as_it_is(tmp_path: Path, event: str, cargo: str) -> None:
    handed: list[Entry] = []
    waits: list[float] = []
    follower = JournalFollower(
        tmp_path, lambda entry, _beta: handed.append(entry), logger, sleep=waits.append
    )
    journal = Journal(tmp_path)
    if cargo in {"ship", "srv"}:
        cargo_file(journal, vessel="SRV" if cargo == "srv" else "Ship")
    journal.write(FIRST, event)
    follower.poll()
    assert handed == [json.loads(event)]
    # Nothing to wait for: the file describes a later event, or is not the ship's, or is missing
    assert waits == []


def test_the_watcher_polls_on_its_own_thread_until_stopped(journal: Journal) -> None:
    seen = threading.Event()
    threads: list[str] = []

    def receive(entry: Entry, _beta: bool) -> None:
        threads.append(threading.current_thread().name)
        seen.set()

    journal.write(FIRST, line("Music"))
    watcher = JournalWatcher(JournalFollower(journal.directory, receive, logger), logger, 0.01)
    watcher.start()
    assert seen.wait(2)
    assert watcher.stop()
    assert threads == ["EDRockMaster journal"]
    with pytest.raises(RuntimeError, match="once"):
        watcher.start()


def test_a_failing_poll_is_logged_and_polling_goes_on(
    journal: Journal, caplog: pytest.LogCaptureFixture
) -> None:
    calls = threading.Semaphore(0)

    class Failing(JournalFollower):
        def poll(self) -> int:
            calls.release()
            raise ValueError("broken")

    watcher = JournalWatcher(Failing(journal.directory, journal.receive, logger), logger, 0.01)
    with caplog.at_level(logging.ERROR):
        watcher.start()
        assert calls.acquire(timeout=2)
        assert calls.acquire(timeout=2)
        watcher.stop()
    assert "broken" in caplog.text


def test_stopping_a_watcher_never_started() -> None:
    assert JournalWatcher(JournalFollower(Path("."), lambda e, b: None, logger), logger).stop()
