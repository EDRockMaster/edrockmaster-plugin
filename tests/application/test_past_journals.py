from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.application.past_journals import (
    EVENTS,
    PROGRESS_EVERY,
    VERSION,
    PastJournalReader,
    PastJournalsRead,
)
from edrockmaster.application.ports import IndexedFile, JournalFile, KeptHistory
from edrockmaster.domain.combat.journal import CommanderDied, Galaxy
from edrockmaster.domain.combat.vouchers import CommanderKey, VoucherLedger
from edrockmaster.domain.journal_reading import Entry

T0 = datetime(2026, 10, 14, 20, 0, tzinfo=UTC)
FUSION = CommanderKey("F1234", Galaxy.LIVE)
LAVIGNY = "Lavigny's Legion"


def stamp(day: int) -> str:
    return f"{(T0 + timedelta(days=day)):%Y-%m-%dT%H:%M:%SZ}"


def header(day: int) -> Entry:
    return {"timestamp": stamp(day), "event": "Fileheader", "part": 1, "gameversion": "4.4.1.1"}


def commander(day: int) -> Entry:
    return {"timestamp": stamp(day), "event": "Commander", "FID": "F1234", "Name": "Fusion"}


def bounty(day: int, reward: int) -> Entry:
    return {
        "timestamp": stamp(day),
        "event": "Bounty",
        "Rewards": [{"Faction": LAVIGNY, "Reward": reward}],
        "TotalReward": reward,
    }


def redeem(day: int, amount: int) -> Entry:
    return {
        "timestamp": stamp(day),
        "event": "RedeemVoucher",
        "Type": "bounty",
        "Amount": amount,
        "Factions": [{"Faction": LAVIGNY, "Amount": amount}],
    }


def died(day: int) -> Entry:
    return {"timestamp": stamp(day), "event": "Died"}


def shutdown(day: int) -> Entry:
    return {"timestamp": stamp(day), "event": "Shutdown"}


def music(day: int) -> Entry:
    return {"timestamp": stamp(day), "event": "Music", "MusicTrack": "Combat"}


def session(day: int, *entries: Entry, closed: bool = True) -> list[Entry]:
    return [header(day), commander(day), *entries, *([shutdown(day)] if closed else [])]


class FakeArchive:
    def __init__(self) -> None:
        self.contents: dict[str, list[Entry]] = {}
        self.sizes: dict[str, int] = {}
        self.reads: list[str] = []
        self.asked: set[frozenset[str]] = set()

    def add(self, day: int, entries: list[Entry]) -> JournalFile:
        name = f"Journal.{(T0 + timedelta(days=day)):%Y-%m-%dT%H%M%S}.01.log"
        self.contents[name] = entries
        self.sizes[name] = len(entries) * 100
        return self._file(name)

    def remove(self, day: int) -> None:
        name = f"Journal.{(T0 + timedelta(days=day)):%Y-%m-%dT%H%M%S}.01.log"
        del self.contents[name]

    def _file(self, name: str) -> JournalFile:
        return JournalFile(name, self.sizes[name])

    def files(self) -> Sequence[JournalFile]:
        return [self._file(name) for name in sorted(self.contents)]

    def entries(self, file: JournalFile, events: frozenset[str]) -> Iterable[Entry]:
        self.reads.append(file.name)
        self.asked.add(events)
        return [entry for entry in self.contents[file.name] if entry["event"] in events]


class FakeStore:
    def __init__(self) -> None:
        self.version = VERSION
        self.files: dict[str, IndexedFile] = {}
        self.ledger = VoucherLedger()
        self.saves = 0
        self.fail_on: str | None = None

    def load(self, version: int) -> KeptHistory:
        if version != self.version:
            return KeptHistory()
        return KeptHistory(dict(self.files), self.ledger.copy())

    def save(self, version: int, indexed: IndexedFile, ledger: VoucherLedger) -> None:
        if indexed.file.name == self.fail_on:
            raise OSError("disk full")
        self.version = version
        self.files[indexed.file.name] = indexed
        self.ledger = ledger.copy()
        self.saves += 1

    def clear(self, version: int) -> None:
        self.version = version
        self.files.clear()
        self.ledger = VoucherLedger()


class Harness:
    def __init__(self) -> None:
        self.archive = FakeArchive()
        self.store = FakeStore()
        self.results: list[PastJournalsRead] = []
        self.reader = self.new_reader()

    def new_reader(self) -> PastJournalReader:
        return PastJournalReader(self.archive, self.store, self.results.append)

    @property
    def last(self) -> PastJournalsRead:
        return self.results[-1]


@pytest.fixture
def harness() -> Harness:
    return Harness()


def test_vouchers_of_past_game_sessions_add_up(harness: Harness) -> None:
    harness.archive.add(0, session(0, bounty(0, 200_000)))
    harness.archive.add(1, session(1, bounty(1, 300_000)))
    harness.archive.add(2, session(2, closed=False))
    harness.reader.catch_up()
    read = harness.last
    assert read.ledger.current.bounties == {LAVIGNY: 500_000}
    assert read.ledger.commander == FUSION
    assert read.indexed == frozenset(harness.archive.contents) - {harness.archive.files()[-1].name}
    assert (read.past.read, read.past.total, read.past.complete) == (3, 3, True)


def test_redemptions_and_deaths_of_past_sessions_count(harness: Harness) -> None:
    harness.archive.add(0, session(0, bounty(0, 200_000), redeem(0, 200_000), bounty(0, 50_000)))
    harness.archive.add(1, session(1, bounty(1, 70_000), died(1)))
    harness.archive.add(2, session(2, bounty(2, 10_000)))
    harness.reader.catch_up()
    assert harness.last.ledger.current.bounties == {LAVIGNY: 10_000}


def test_only_the_events_that_matter_are_read(harness: Harness) -> None:
    harness.archive.add(0, session(0, music(0), bounty(0, 1_000)))
    harness.reader.catch_up()
    assert harness.archive.asked == {EVENTS}
    assert {"Bounty", "FactionKillBond", "CapShipBond", "RedeemVoucher", "Died"} <= EVENTS
    assert {"Fileheader", "Commander", "LoadGame", "Shutdown"} <= EVENTS


def test_the_current_file_is_left_to_the_live_reading(harness: Harness) -> None:
    harness.archive.add(0, session(0, bounty(0, 1_000)))
    current = harness.archive.add(1, session(1, bounty(1, 2_000), closed=False))
    harness.reader.catch_up()
    assert current.name not in harness.store.files
    assert harness.last.ledger.current.bounties == {LAVIGNY: 1_000}


def test_a_newest_file_closed_by_the_game_is_complete(harness: Harness) -> None:
    newest = harness.archive.add(0, session(0, bounty(0, 1_000)))
    harness.reader.catch_up()
    assert newest.name in harness.last.indexed


def test_each_file_is_kept_with_the_commander_at_its_end(harness: Harness) -> None:
    first = harness.archive.add(0, session(0, bounty(0, 1_000)))
    harness.archive.add(1, session(1, closed=False))
    harness.reader.catch_up()
    assert harness.store.files == {first.name: IndexedFile(first, FUSION)}
    assert harness.store.ledger.current.bounties == {LAVIGNY: 1_000}


def test_a_later_start_reads_the_new_files_only(harness: Harness) -> None:
    harness.archive.add(0, session(0, bounty(0, 1_000)))
    harness.archive.add(1, session(1, closed=False))
    harness.reader.catch_up()
    harness.archive.contents[harness.archive.files()[-1].name].append(shutdown(1))
    harness.archive.add(2, session(2, bounty(2, 4_000)))
    harness.archive.reads.clear()
    later = harness.new_reader()
    later.catch_up()
    assert harness.archive.reads == [
        harness.archive.files()[1].name,
        harness.archive.files()[2].name,
    ]
    assert harness.last.ledger.current.bounties == {LAVIGNY: 5_000}


def test_reading_again_with_nothing_new_reads_nothing(harness: Harness) -> None:
    harness.archive.add(0, session(0, bounty(0, 1_000)))
    harness.reader.catch_up()
    harness.archive.reads.clear()
    harness.reader.catch_up()
    assert harness.archive.reads == []
    assert harness.last.ledger.current.bounties == {LAVIGNY: 1_000}


def test_a_part_without_a_commander_goes_on_with_the_previous_one(harness: Harness) -> None:
    harness.archive.add(0, session(0, bounty(0, 1_000), closed=False))
    harness.archive.add(1, [header(1), bounty(1, 2_000), shutdown(1)])
    harness.reader.catch_up()
    assert harness.store.ledger.books == {FUSION: harness.last.ledger.current}
    assert harness.last.ledger.current.bounties == {LAVIGNY: 3_000}


def test_a_file_read_counts_once_even_from_a_new_reader(harness: Harness) -> None:
    harness.archive.add(0, session(0, bounty(0, 1_000)))
    harness.reader.catch_up()
    harness.new_reader().catch_up()
    assert harness.last.ledger.current.bounties == {LAVIGNY: 1_000}
    assert harness.store.saves == 1


def test_a_failed_save_leaves_the_file_to_read_again(harness: Harness) -> None:
    harness.archive.add(0, session(0, bounty(0, 1_000)))
    failing = harness.archive.add(1, session(1, bounty(1, 2_000)))
    harness.store.fail_on = failing.name
    with pytest.raises(OSError, match="disk full"):
        harness.reader.catch_up()
    assert harness.store.ledger.current.bounties == {LAVIGNY: 1_000}
    harness.store.fail_on = None
    harness.new_reader().catch_up()
    assert harness.last.ledger.current.bounties == {LAVIGNY: 3_000}


def test_a_file_whose_size_changed_reads_everything_again(harness: Harness) -> None:
    first = harness.archive.add(0, session(0, bounty(0, 1_000)))
    harness.archive.add(1, session(1, bounty(1, 2_000)))
    harness.reader.catch_up()
    harness.archive.contents[first.name] = session(0, bounty(0, 5_000))
    harness.archive.sizes[first.name] += 1
    harness.new_reader().catch_up()
    assert harness.last.ledger.current.bounties == {LAVIGNY: 7_000}


def test_an_older_file_put_back_reads_everything_again(harness: Harness) -> None:
    harness.archive.add(1, session(1, bounty(1, 2_000)))
    harness.reader.catch_up()
    harness.archive.add(0, session(0, bounty(0, 1_000), died(0)))
    harness.reader.catch_up()
    assert harness.last.ledger.current.bounties == {LAVIGNY: 2_000}


def test_files_removed_from_the_folder_keep_what_they_gave(harness: Harness) -> None:
    harness.archive.add(0, session(0, bounty(0, 1_000)))
    harness.archive.add(1, session(1, bounty(1, 2_000)))
    harness.reader.catch_up()
    harness.archive.remove(0)
    harness.archive.add(2, session(2, bounty(2, 4_000)))
    harness.new_reader().catch_up()
    assert harness.last.ledger.current.bounties == {LAVIGNY: 7_000}


def test_a_store_of_other_rules_is_read_again(harness: Harness) -> None:
    harness.archive.add(0, session(0, bounty(0, 1_000)))
    harness.store.version = VERSION - 1
    harness.store.files = {f.name: IndexedFile(f, FUSION) for f in harness.archive.files()}
    harness.reader.catch_up()
    assert harness.store.version == VERSION
    assert harness.last.ledger.current.bounties == {LAVIGNY: 1_000}


def test_reading_again_forgets_what_was_kept(harness: Harness) -> None:
    harness.archive.add(0, session(0, bounty(0, 1_000)))
    harness.reader.catch_up()
    harness.store.ledger = VoucherLedger()  # as if a fixed rule now read nothing
    harness.archive.reads.clear()
    harness.reader.read_again()
    assert harness.archive.reads == [harness.archive.files()[0].name]
    assert harness.store.saves == 2
    assert harness.last.ledger.current.bounties == {LAVIGNY: 1_000}
    assert [r.past.read for r in harness.results[-2:]] == [0, 1]


def test_progress_is_told_as_the_files_are_read(harness: Harness) -> None:
    for day in range(PROGRESS_EVERY * 2 + 1):
        harness.archive.add(day, session(day, bounty(day, 1_000)))
    harness.reader.catch_up()
    reads = [(r.past.read, r.past.total) for r in harness.results]
    total = PROGRESS_EVERY * 2 + 1
    assert reads == [
        (0, total),
        (PROGRESS_EVERY, total),
        (PROGRESS_EVERY * 2, total),
        (total, total),
    ]
    assert not harness.results[0].past.complete
    assert harness.results[1].ledger.current.bounties == {LAVIGNY: 1_000 * PROGRESS_EVERY}


def test_an_empty_folder_is_complete_at_once(harness: Harness) -> None:
    harness.reader.catch_up()
    assert harness.last.past.complete
    assert harness.last.ledger.current.total == 0


def test_results_are_copies(harness: Harness) -> None:
    harness.archive.add(0, session(0, bounty(0, 1_000)))
    harness.reader.catch_up()
    harness.last.ledger.apply(CommanderDied(T0))
    harness.reader.catch_up()
    assert harness.last.ledger.current.bounties == {LAVIGNY: 1_000}
