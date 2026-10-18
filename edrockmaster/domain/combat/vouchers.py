"""Unredeemed vouchers, per commander and galaxy, across game sessions (ADR 0013, ADR 0052).

The journal never restates the vouchers held: they are only known by following
them, from the moment they are earned (``Bounty``, ``FactionKillBond``,
``CapShipBond``) to the moment they are paid (``RedeemVoucher``) or lost
(``Died``). ``VoucherLedger`` follows them for every commander the journal names,
in each galaxy (the live game and Legacy are separate saves), so that the
journals of past game sessions, read once, give what the commander still holds.

A redemption pays every voucher of the faction (ADR 0049): a broker pays less
than the vouchers, and combat bonds are paid more than the journal wrote; in
both cases, nothing of that faction is left.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from edrockmaster.domain.combat.journal import (
    BountyAwarded,
    CombatBondAwarded,
    CommanderDied,
    Fact,
    FactionReward,
    Galaxy,
    GameIdentified,
    VoucherKind,
    VouchersRedeemed,
)

UNKNOWN_COMMANDER = ""
"""The Frontier id of vouchers earned before the journal named anyone (journals before 3.0)."""


@dataclass(frozen=True, slots=True)
class CommanderKey:
    """One save of a commander: their Frontier id, in a galaxy."""

    fid: str
    galaxy: Galaxy


@dataclass(frozen=True, slots=True)
class HeldVoucher:
    """The vouchers of one kind a faction will pay, held since the oldest of them."""

    kind: VoucherKind
    faction: str
    amount: int
    since: datetime


@dataclass(frozen=True, slots=True)
class Vouchers:
    """The vouchers a commander holds, the oldest first."""

    held: tuple[HeldVoucher, ...] = ()

    @property
    def total(self) -> int:
        return sum(voucher.amount for voucher in self.held)

    @property
    def bounties(self) -> Mapping[str, int]:
        return self._of(VoucherKind.BOUNTY)

    @property
    def combat_bonds(self) -> Mapping[str, int]:
        return self._of(VoucherKind.COMBAT_BOND)

    def _of(self, kind: VoucherKind) -> Mapping[str, int]:
        return MappingProxyType({v.faction: v.amount for v in self.held if v.kind is kind})


@dataclass(frozen=True, slots=True)
class PastJournals:
    """How far the journals of past game sessions were read (ADR 0052)."""

    read: int
    total: int

    @property
    def complete(self) -> bool:
        return self.read >= self.total


NOT_READ_YET = PastJournals(read=0, total=1)
"""Before the journals of past game sessions were even listed."""


@dataclass(frozen=True, slots=True)
class VouchersUpdated:
    """The vouchers the current commander holds, and from which journals they are known."""

    vouchers: Vouchers
    past: PastJournals


type _Book = dict[tuple[VoucherKind, str], HeldVoucher]


class VoucherLedger:
    """Aggregate root: every commander's unredeemed vouchers, and who plays now."""

    def __init__(self) -> None:
        self._books: dict[CommanderKey, _Book] = {}
        self._commander = CommanderKey(UNKNOWN_COMMANDER, Galaxy.LIVE)

    @classmethod
    def restore(
        cls, books: Mapping[CommanderKey, Vouchers], commander: CommanderKey
    ) -> VoucherLedger:
        """The ledger as it was kept: its books, and who played last."""
        ledger = cls()
        ledger._commander = commander
        for key, vouchers in books.items():
            ledger._books[key] = {(v.kind, v.faction): v for v in vouchers.held}
        return ledger

    @property
    def commander(self) -> CommanderKey:
        return self._commander

    @property
    def current(self) -> Vouchers:
        return _vouchers(self._books.get(self._commander, {}))

    @property
    def books(self) -> Mapping[CommanderKey, Vouchers]:
        """The vouchers of every commander who holds some."""
        return MappingProxyType({key: _vouchers(book) for key, book in self._books.items() if book})

    def copy(self) -> VoucherLedger:
        return VoucherLedger.restore(self.books, self._commander)

    def apply(self, fact: Fact) -> bool:
        """Follow a fact of the journal; ``True`` when the current vouchers changed."""
        match fact:
            case GameIdentified(fid=fid, galaxy=galaxy):
                before = self._commander
                self._commander = CommanderKey(
                    fid or before.fid, galaxy if galaxy is not None else before.galaxy
                )
                return self._commander != before
            case BountyAwarded(at=at, rewards=rewards):
                return self._earn(VoucherKind.BOUNTY, rewards, at)
            case CombatBondAwarded(at=at, amount=amount, awarding_faction=faction):
                return self._earn(VoucherKind.COMBAT_BOND, (FactionReward(faction, amount),), at)
            case VouchersRedeemed(kind=kind, by_faction=paid):
                book = self._books.get(self._commander, {})
                paid_off = [book.pop((kind, reward.faction), None) for reward in paid]
                return any(paid_off)
            case CommanderDied():
                return bool(self._books.pop(self._commander, None))
            case _:
                return False

    def _earn(self, kind: VoucherKind, rewards: tuple[FactionReward, ...], at: datetime) -> bool:
        book = self._books.setdefault(self._commander, {})
        for reward in rewards:
            held = book.get((kind, reward.faction))
            book[(kind, reward.faction)] = HeldVoucher(
                kind,
                reward.faction,
                (held.amount if held else 0) + reward.amount,
                held.since if held else at,
            )
        return bool(rewards)


def _vouchers(book: _Book) -> Vouchers:
    """Oldest first; then in the same order, whatever the order they were stored in."""
    return Vouchers(tuple(sorted(book.values(), key=lambda v: (v.since, v.kind.value, v.faction))))
