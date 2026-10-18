"""The past journals' index and vouchers in a real SQLite file, through the real I/O thread."""

import logging
import sqlite3
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from edrockmaster.application.ports import IndexedFile, JournalFile, PastJournalStore
from edrockmaster.domain.combat.journal import (
    BountyAwarded,
    CombatBondAwarded,
    FactionReward,
    Galaxy,
    GameIdentified,
)
from edrockmaster.domain.combat.vouchers import CommanderKey, VoucherLedger
from edrockmaster.infrastructure.database import FILE_NAME, LocalDatabase
from edrockmaster.infrastructure.past_journal_store import SqlitePastJournalStore
from edrockmaster.infrastructure.worker import IoWorker

logger = logging.getLogger("test.past_journals")

AT = datetime(2026, 10, 14, 20, 41, 12, tzinfo=UTC)
READ_AT = datetime(2026, 10, 18, 8, 31, 57, tzinfo=UTC)
FUSION = CommanderKey("F1234", Galaxy.LIVE)
LEGACY = CommanderKey("F1234", Galaxy.LEGACY)
FIRST = JournalFile("Journal.2026-10-14T203648.01.log", 182_044)
SECOND = JournalFile("Journal.2026-10-15T190949.01.log", 9_120)


def ledger() -> VoucherLedger:
    kept = VoucherLedger()
    kept.apply(GameIdentified(AT, "F1234", Galaxy.LIVE))
    kept.apply(
        BountyAwarded(
            AT,
            33_599_400,
            (FactionReward("Lavigny's Legion", 33_552_700), FactionReward("", 46_700)),
            None,
            None,
            False,
        )
    )
    kept.apply(GameIdentified(AT, None, Galaxy.LEGACY))
    kept.apply(CombatBondAwarded(AT, 5_000, "Federation", None, kill=True))
    kept.apply(GameIdentified(AT, None, Galaxy.LIVE))
    return kept


class Storage:
    def __init__(self, directory: Path) -> None:
        self.database = LocalDatabase(directory / FILE_NAME, logger)
        self.worker = IoWorker(logger)
        self.worker.start()
        self.store: PastJournalStore = SqlitePastJournalStore(
            self.database, self.worker, logger, now=lambda: READ_AT
        )

    def open(self) -> None:
        assert self.worker.call(self.database.open).available

    def close(self) -> None:
        if self.worker.is_running:
            self.worker.call(self.database.close)
            self.worker.stop()


@pytest.fixture
def storage(tmp_path: Path) -> Iterator[Storage]:
    storage = Storage(tmp_path)
    storage.open()
    yield storage
    storage.close()


def test_a_new_database_has_nothing_kept(storage: Storage) -> None:
    kept = storage.store.load(1)
    assert kept.files == {}
    assert kept.ledger.books == {}


def test_a_file_and_its_ledger_are_kept_together(storage: Storage, tmp_path: Path) -> None:
    storage.store.save(1, IndexedFile(FIRST, FUSION), ledger())
    storage.close()
    again = Storage(tmp_path)
    again.open()
    kept = again.store.load(1)
    again.close()
    assert kept.files == {FIRST.name: IndexedFile(FIRST, FUSION)}
    assert kept.ledger.books == ledger().books
    assert kept.ledger.commander == FUSION
    assert kept.ledger.current.bounties == {"Lavigny's Legion": 33_552_700, "": 46_700}
    assert kept.ledger.current.held[0].since == AT


def test_each_save_replaces_the_vouchers(storage: Storage) -> None:
    storage.store.save(1, IndexedFile(FIRST, FUSION), ledger())
    storage.store.save(1, IndexedFile(SECOND, LEGACY), VoucherLedger.restore({}, LEGACY))
    kept = storage.store.load(1)
    assert set(kept.files) == {FIRST.name, SECOND.name}
    assert kept.ledger.books == {}
    assert kept.ledger.commander == LEGACY


def test_another_version_of_the_rules_finds_nothing_and_forgets_it(storage: Storage) -> None:
    storage.store.save(1, IndexedFile(FIRST, FUSION), ledger())
    assert storage.store.load(2).files == {}
    assert storage.store.load(1).files == {}


def test_clearing_forgets_everything(storage: Storage) -> None:
    storage.store.save(1, IndexedFile(FIRST, FUSION), ledger())
    storage.store.clear(1)
    kept = storage.store.load(1)
    assert (kept.files, kept.ledger.books) == ({}, {})


def test_a_failed_save_leaves_nothing_half_written(
    storage: Storage, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage.store.save(1, IndexedFile(FIRST, FUSION), ledger())
    monkeypatch.setattr(
        "edrockmaster.infrastructure.past_journal_store._voucher_rows",
        lambda _ledger: [("F1234", "live", "bounty", "Lavigny's Legion", 0, AT.isoformat())],
    )
    with pytest.raises(Exception, match="CHECK constraint failed"):
        storage.store.save(1, IndexedFile(SECOND, FUSION), ledger())
    monkeypatch.undo()
    kept = storage.store.load(1)
    assert set(kept.files) == {FIRST.name}
    assert kept.ledger.books == ledger().books


def test_the_database_is_used_on_the_io_thread_only(storage: Storage) -> None:
    seen: list[str] = []
    original = storage.database.connection

    def connection() -> sqlite3.Connection:
        seen.append(threading.current_thread().name)
        return original()

    storage.database.connection = connection  # type: ignore[method-assign]
    storage.store.save(1, IndexedFile(FIRST, FUSION), ledger())
    storage.store.load(1)
    assert set(seen) == {"EDRockMaster I/O"}


def test_without_a_database_nothing_is_kept_and_nothing_fails(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    storage = Storage(tmp_path)  # never opened
    with caplog.at_level(logging.WARNING):
        storage.store.save(1, IndexedFile(FIRST, FUSION), ledger())
        storage.store.clear(1)
        assert storage.store.load(1).files == {}
    storage.worker.stop()
    assert "past journals are read again at each start" in caplog.text
