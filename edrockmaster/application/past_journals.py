"""Reading the journals of past game sessions once, and keeping what lasts (ADR 0052).

``PastJournalReader`` goes through the journal files the index does not know,
oldest first, and folds the facts that cross game sessions (the vouchers, and
who plays) into a ``VoucherLedger``. A file is **complete** once the game no
longer writes it: a newer file exists, or it ends with ``Shutdown``. Each
complete file is indexed with the ledger it led to, together: a file is counted
in full or not at all. The current file is left to the live reading.

A file of the index whose size changed, or a file older than the newest one of
the index that the index does not know (put back in the folder), means the
order of the facts is no longer known: everything is read again, from the files
present. Files removed from the folder keep what they gave, otherwise.

The ports block: the reader runs on a thread of its own, never on the core's.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from edrockmaster.application.ports import (
    IndexedFile,
    JournalArchive,
    JournalFile,
    KeptHistory,
    PastJournalStore,
)
from edrockmaster.domain.combat.journal import parse_entry
from edrockmaster.domain.combat.vouchers import PastJournals, VoucherLedger

VERSION = 1
"""The version of the rules that read the vouchers from the journal: raised by a fix that
changes what a file gives, so that every file is read again."""

EVENTS = frozenset(
    {
        "Fileheader",
        "Commander",
        "LoadGame",
        "Bounty",
        "FactionKillBond",
        "CapShipBond",
        "RedeemVoucher",
        "Died",
        "Shutdown",
    }
)
"""The events of past journals worth decoding: the others are skipped by their name."""

PROGRESS_EVERY = 20
"""Files read between two reports of the progress."""

_CLOSED = "Shutdown"


@dataclass(frozen=True, slots=True)
class PastJournalsRead:
    """Where the reading of past journals stands: what it gave, from which files."""

    ledger: VoucherLedger
    """A copy: the reader goes on with its own."""
    indexed: frozenset[str]
    """The names of the files counted in ``ledger``."""
    past: PastJournals


class PastJournalReader:
    def __init__(
        self,
        archive: JournalArchive,
        store: PastJournalStore,
        on_read: Callable[[PastJournalsRead], None],
    ) -> None:
        """``on_read`` receives the progress, then the result, on the reader's thread."""
        self._archive = archive
        self._store = store
        self._on_read = on_read
        self._kept: KeptHistory | None = None

    def catch_up(self) -> None:
        """Read the complete files the index does not know yet."""
        kept = self._kept if self._kept is not None else self._store.load(VERSION)
        self._kept = kept
        files = self._archive.files()
        if self._out_of_order(kept, files):
            self._store.clear(VERSION)
            kept = self._kept = KeptHistory()
        pending = [file for file in files if file.name not in kept.files]
        done = len(files) - len(pending)
        if pending:
            self._report(kept, done, len(files))
        for count, file in enumerate(pending, start=1):
            ledger = kept.ledger.copy()
            if not self._fold(file, ledger, newest=file is files[-1]):
                break  # the current file: the live reading has it
            indexed = IndexedFile(file, ledger.commander)
            self._store.save(VERSION, indexed, ledger)
            kept.files[file.name] = indexed
            kept.ledger = ledger
            if count % PROGRESS_EVERY == 0 and count < len(pending):
                self._report(kept, done + count, len(files))
        self._report(kept, len(files), len(files))

    def read_again(self) -> None:
        """Forget what was kept and read every file of the folder again."""
        self._store.clear(VERSION)
        self._kept = KeptHistory()
        self.catch_up()

    def _fold(self, file: JournalFile, ledger: VoucherLedger, *, newest: bool) -> bool:
        """Fold a file's facts into the ledger; ``False`` if the file is not complete."""
        last = None
        for entry in self._archive.entries(file, EVENTS):
            last = entry.get("event")
            fact = parse_entry(entry)
            if fact is not None:
                ledger.apply(fact)
        return not newest or last == _CLOSED

    @staticmethod
    def _out_of_order(kept: KeptHistory, files: Sequence[JournalFile]) -> bool:
        """A file of the index changed, or an unknown one comes before the newest it knows."""
        newest = -1
        for position, file in enumerate(files):
            indexed = kept.files.get(file.name)
            if indexed is not None:
                if indexed.file.size != file.size:
                    return True
                newest = position
        return any(file.name not in kept.files for file in files[:newest])

    def _report(self, kept: KeptHistory, read: int, total: int) -> None:
        self._on_read(
            PastJournalsRead(kept.ledger.copy(), frozenset(kept.files), PastJournals(read, total))
        )
