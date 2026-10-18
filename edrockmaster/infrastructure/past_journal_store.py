"""The index of the journals of past game sessions, and what they gave (ADR 0018, ADR 0052).

``SqlitePastJournalStore`` implements the application's ``PastJournalStore``:
its reader runs on a thread that may wait, so each call runs on the I/O thread
and waits for it. The functions below are the SQL, run on the I/O thread only.

A file read and the vouchers it led to are written in one transaction. Without
a local database (it could not be opened), nothing is kept: the reader then
reads every past journal at each start, and the figures stay right.
"""

from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from edrockmaster.application.ports import IndexedFile, JournalFile, KeptHistory
from edrockmaster.domain.combat.journal import Galaxy, VoucherKind
from edrockmaster.domain.combat.vouchers import (
    CommanderKey,
    HeldVoucher,
    VoucherLedger,
    Vouchers,
)
from edrockmaster.infrastructure.database import (
    DatabaseUnavailableError,
    LocalDatabase,
    transaction,
)

type _VoucherRow = tuple[str, str, str, str, int, str]


class Caller(Protocol):
    def call[T](self, job: Callable[[], T]) -> T:
        """Run a job on the I/O thread and wait for its result."""
        ...


def _now() -> datetime:
    return datetime.now(UTC)


class SqlitePastJournalStore:
    def __init__(
        self,
        database: LocalDatabase,
        io: Caller,
        logger: logging.Logger,
        now: Callable[[], datetime] = _now,
    ) -> None:
        self._database = database
        self._io = io
        self._logger = logger
        self._now = now
        self._unavailable_logged = False

    def load(self, version: int) -> KeptHistory:
        kept = self._run(lambda connection: read_history(connection, version))
        return kept if kept is not None else KeptHistory()

    def save(self, version: int, indexed: IndexedFile, ledger: VoucherLedger) -> None:
        read_at = self._now()
        self._run(lambda connection: write_file(connection, version, indexed, ledger, read_at))

    def clear(self, version: int) -> None:
        self._run(lambda connection: clear_history(connection, version))

    def _run[T](self, job: Callable[[sqlite3.Connection], T]) -> T | None:
        try:
            return self._io.call(lambda: job(self._database.connection()))
        except DatabaseUnavailableError:
            if not self._unavailable_logged:
                self._logger.warning(
                    "No local database: past journals are read again at each start"
                )
                self._unavailable_logged = True
            return None


def read_history(connection: sqlite3.Connection, version: int) -> KeptHistory:
    """What was kept under that version of the rules; under another, it is forgotten."""
    state = connection.execute("SELECT version, commander, galaxy FROM past_journals").fetchone()
    if state is None or state[0] != version:
        clear_history(connection, version)
        return KeptHistory()
    _, fid, galaxy = state
    files = {
        name: IndexedFile(JournalFile(name, size), CommanderKey(commander, Galaxy(file_galaxy)))
        for name, size, commander, file_galaxy in connection.execute(
            "SELECT name, size, commander, galaxy FROM journal_file_read"
        )
    }
    books: defaultdict[CommanderKey, list[HeldVoucher]] = defaultdict(list)
    for commander, voucher_galaxy, kind, faction, amount, since in connection.execute(
        "SELECT commander, galaxy, kind, faction, amount, since FROM unredeemed_voucher"
        " ORDER BY since, kind, faction"
    ):
        books[CommanderKey(commander, Galaxy(voucher_galaxy))].append(
            HeldVoucher(VoucherKind(kind), faction, amount, datetime.fromisoformat(since))
        )
    ledger = VoucherLedger.restore(
        {key: Vouchers(tuple(held)) for key, held in books.items()},
        CommanderKey(fid, Galaxy(galaxy)),
    )
    return KeptHistory(files, ledger)


def write_file(
    connection: sqlite3.Connection,
    version: int,
    indexed: IndexedFile,
    ledger: VoucherLedger,
    read_at: datetime,
) -> None:
    """Index a file and keep the vouchers it led to, together."""
    commander = ledger.commander
    with transaction(connection):
        connection.execute(
            "INSERT OR REPLACE INTO journal_file_read (name, size, commander, galaxy, read_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                indexed.file.name,
                indexed.file.size,
                indexed.commander.fid,
                indexed.commander.galaxy.value,
                read_at.astimezone(UTC).isoformat(),
            ),
        )
        connection.execute("DELETE FROM unredeemed_voucher")
        connection.executemany(
            "INSERT INTO unredeemed_voucher (commander, galaxy, kind, faction, amount, since)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            _voucher_rows(ledger),
        )
        connection.execute(
            "INSERT OR REPLACE INTO past_journals (id, version, commander, galaxy)"
            " VALUES (1, ?, ?, ?)",
            (version, commander.fid, commander.galaxy.value),
        )


def clear_history(connection: sqlite3.Connection, version: int) -> None:
    with transaction(connection):
        connection.execute("DELETE FROM journal_file_read")
        connection.execute("DELETE FROM unredeemed_voucher")
        connection.execute(
            "INSERT OR REPLACE INTO past_journals (id, version, commander, galaxy)"
            " VALUES (1, ?, '', ?)",
            (version, Galaxy.LIVE.value),
        )


def _voucher_rows(ledger: VoucherLedger) -> list[_VoucherRow]:
    return [
        (
            key.fid,
            key.galaxy.value,
            voucher.kind.value,
            voucher.faction,
            voucher.amount,
            voucher.since.astimezone(UTC).isoformat(),
        )
        for key, vouchers in ledger.books.items()
        for voucher in vouchers.held
    ]
