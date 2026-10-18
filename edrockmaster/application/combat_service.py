"""Use cases of the combat assistant.

The unredeemed vouchers are those of the journals of past game sessions, as
``PastJournalReader`` hands them over (ADR 0052), followed by the facts of the
files it has not counted yet: the current one, read live. Each fact is noted
with its file, so that a file the reader counts later is never counted twice.
"""

from __future__ import annotations

from typing import TypeIs

from edrockmaster.application.past_journals import PastJournalsRead
from edrockmaster.application.ports import Clock
from edrockmaster.domain.combat.journal import (
    BountyAwarded,
    CombatBondAwarded,
    CommanderDied,
    Fact,
    GameIdentified,
    VouchersRedeemed,
    parse_entry,
)
from edrockmaster.domain.combat.session import (
    CombatNotification,
    CombatStats,
    CombatTracker,
)
from edrockmaster.domain.combat.vouchers import (
    NOT_READ_YET,
    PastJournals,
    VoucherLedger,
    Vouchers,
    VouchersUpdated,
)
from edrockmaster.domain.journal_reading import Entry

type _VoucherFact = (
    BountyAwarded | CombatBondAwarded | VouchersRedeemed | CommanderDied | GameIdentified
)
_VOUCHER_FACTS = (BountyAwarded, CombatBondAwarded, VouchersRedeemed, CommanderDied, GameIdentified)


class CombatService:
    """Called on the core thread only; pure computation."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._tracker = CombatTracker()
        self._past = NOT_READ_YET
        self._base = VoucherLedger()
        self._ledger = VoucherLedger()
        self._file: str | None = None
        self._live: list[tuple[str | None, _VoucherFact]] = []
        """The facts of the files the past journals do not count yet, with their file."""

    @property
    def current_stats(self) -> CombatStats | None:
        session = self._tracker.session
        return session.stats if session is not None else None

    @property
    def vouchers(self) -> Vouchers:
        return self._ledger.current

    @property
    def past_journals(self) -> PastJournals:
        return self._past

    def journal_file_opened(self, name: str) -> None:
        """The entries that follow come from that journal file."""
        self._file = name

    def handle_journal_entry(self, entry: Entry) -> list[CombatNotification | VouchersUpdated]:
        fact = parse_entry(entry)
        if fact is None:
            return []
        notifications: list[CombatNotification | VouchersUpdated] = []
        notifications += self._tracker.handle(fact)
        if _follows_vouchers(fact):
            self._live.append((self._file, fact))
            if self._ledger.apply(fact):
                notifications.append(self._vouchers_updated())
        return notifications

    def past_journals_read(self, read: PastJournalsRead) -> list[VouchersUpdated]:
        """The past journals' reading went on: their vouchers, then those read live since."""
        self._past, self._base = read.past, read.ledger
        self._live = [(file, fact) for file, fact in self._live if file not in read.indexed]
        self._ledger = self._base.copy()
        for _, fact in self._live:
            self._ledger.apply(fact)
        return [self._vouchers_updated()]

    def reset_session(self) -> list[CombatNotification]:
        ended = self._tracker.reset(self._clock.now())
        return [ended] if ended is not None else []

    def _vouchers_updated(self) -> VouchersUpdated:
        return VouchersUpdated(self._ledger.current, self._past)


def _follows_vouchers(fact: Fact) -> TypeIs[_VoucherFact]:
    return isinstance(fact, _VOUCHER_FACTS)
