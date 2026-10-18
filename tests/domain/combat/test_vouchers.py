from datetime import UTC, datetime, timedelta

from edrockmaster.domain.combat.journal import (
    BountyAwarded,
    CombatBondAwarded,
    CommanderDied,
    FactionReward,
    Galaxy,
    GameIdentified,
    VoucherKind,
    VouchersRedeemed,
)
from edrockmaster.domain.combat.vouchers import (
    UNKNOWN_COMMANDER,
    CommanderKey,
    HeldVoucher,
    VoucherLedger,
    Vouchers,
)

T0 = datetime(2026, 10, 14, 20, 0, tzinfo=UTC)
LAVIGNY = "Lavigny's Legion"
OLKER = "Olker General Solutions"
FUSION = CommanderKey("F1234", Galaxy.LIVE)
OTHER = CommanderKey("F9999", Galaxy.LIVE)
FUSION_LEGACY = CommanderKey("F1234", Galaxy.LEGACY)


def at(days: float) -> datetime:
    return T0 + timedelta(days=days)


def bounty(days: float, *rewards: tuple[str, int]) -> BountyAwarded:
    return BountyAwarded(
        at=at(days),
        total=sum(amount for _, amount in rewards),
        rewards=tuple(FactionReward(faction, amount) for faction, amount in rewards),
        target="Anaconda",
        victim_faction="Pirates",
        shared=False,
    )


def bond(days: float, amount: int, faction: str = LAVIGNY, kill: bool = True) -> CombatBondAwarded:
    return CombatBondAwarded(
        at=at(days), amount=amount, awarding_faction=faction, victim_faction=None, kill=kill
    )


def redeemed(days: float, kind: VoucherKind, *paid: tuple[str, int]) -> VouchersRedeemed:
    return VouchersRedeemed(
        at=at(days),
        kind=kind,
        amount=sum(amount for _, amount in paid),
        by_faction=tuple(FactionReward(faction, amount) for faction, amount in paid),
    )


def identified(days: float, key: CommanderKey) -> GameIdentified:
    return GameIdentified(at(days), key.fid, key.galaxy)


def ledger_of(key: CommanderKey = FUSION) -> VoucherLedger:
    ledger = VoucherLedger()
    ledger.apply(identified(0, key))
    return ledger


def test_vouchers_add_up_per_kind_and_paying_faction_since_the_first() -> None:
    ledger = ledger_of()
    assert ledger.apply(bounty(0, (LAVIGNY, 200_000), (OLKER, 46_700)))
    assert ledger.apply(bounty(1, (LAVIGNY, 300_000)))
    assert ledger.apply(bond(2, 50_000))
    assert ledger.current == Vouchers(
        (
            HeldVoucher(VoucherKind.BOUNTY, LAVIGNY, 500_000, at(0)),
            HeldVoucher(VoucherKind.BOUNTY, OLKER, 46_700, at(0)),
            HeldVoucher(VoucherKind.COMBAT_BOND, LAVIGNY, 50_000, at(2)),
        )
    )
    assert ledger.current.total == 596_700
    assert ledger.current.bounties == {LAVIGNY: 500_000, OLKER: 46_700}
    assert ledger.current.combat_bonds == {LAVIGNY: 50_000}


def test_a_bond_on_a_capital_ship_is_a_voucher_too() -> None:
    ledger = ledger_of()
    ledger.apply(bond(0, 80_000, kill=False))
    assert ledger.current.combat_bonds == {LAVIGNY: 80_000}


def test_a_redemption_pays_every_voucher_of_the_faction() -> None:
    """With a broker, the game pays less than the vouchers: nothing of them is left."""
    ledger = ledger_of()
    ledger.apply(bounty(0, (LAVIGNY, 400_000), (OLKER, 46_700)))
    ledger.apply(bond(0, 50_000))
    assert ledger.apply(redeemed(1, VoucherKind.BOUNTY, (LAVIGNY, 300_000)))
    assert ledger.current.bounties == {OLKER: 46_700}
    assert ledger.current.combat_bonds == {LAVIGNY: 50_000}


def test_a_redemption_pays_every_faction_it_lists() -> None:
    ledger = ledger_of()
    ledger.apply(bounty(0, (LAVIGNY, 400_000), (OLKER, 46_700)))
    ledger.apply(redeemed(1, VoucherKind.BOUNTY, (LAVIGNY, 400_000), (OLKER, 46_700)))
    assert ledger.current == Vouchers()


def test_a_redemption_of_vouchers_never_seen_changes_nothing() -> None:
    ledger = ledger_of()
    ledger.apply(bounty(0, (OLKER, 46_700)))
    assert not ledger.apply(redeemed(1, VoucherKind.BOUNTY, (LAVIGNY, 90_000)))
    assert ledger.current.bounties == {OLKER: 46_700}


def test_vouchers_earned_again_after_a_redemption_count_from_then() -> None:
    ledger = ledger_of()
    ledger.apply(bounty(0, (LAVIGNY, 100_000)))
    ledger.apply(redeemed(1, VoucherKind.BOUNTY, (LAVIGNY, 100_000)))
    ledger.apply(bounty(2, (LAVIGNY, 70_000)))
    assert ledger.current.held == (HeldVoucher(VoucherKind.BOUNTY, LAVIGNY, 70_000, at(2)),)


def test_death_loses_every_voucher_of_the_commander() -> None:
    ledger = ledger_of()
    ledger.apply(bounty(0, (LAVIGNY, 100_000)))
    assert ledger.apply(CommanderDied(at(1)))
    assert ledger.current == Vouchers()
    assert not ledger.apply(CommanderDied(at(2)))


def test_each_commander_has_their_own_vouchers() -> None:
    ledger = ledger_of(FUSION)
    ledger.apply(bounty(0, (LAVIGNY, 100_000)))
    ledger.apply(identified(1, OTHER))
    assert ledger.current == Vouchers()
    ledger.apply(bounty(1, (OLKER, 5_000)))
    ledger.apply(CommanderDied(at(2)))
    ledger.apply(identified(3, FUSION))
    assert ledger.current.bounties == {LAVIGNY: 100_000}


def test_legacy_and_live_are_separate_saves() -> None:
    ledger = ledger_of(FUSION)
    ledger.apply(bounty(0, (LAVIGNY, 100_000)))
    assert ledger.apply(GameIdentified(at(1), None, Galaxy.LEGACY))
    assert ledger.commander == FUSION_LEGACY
    assert ledger.current == Vouchers()


def test_a_new_commander_and_galaxy_change_the_vouchers_shown() -> None:
    ledger = ledger_of(FUSION)
    assert not ledger.apply(identified(1, FUSION))
    assert ledger.apply(GameIdentified(at(1), "F9999", None))
    assert ledger.commander == OTHER


def test_vouchers_before_any_commander_belong_to_an_unknown_one() -> None:
    ledger = VoucherLedger()
    ledger.apply(bounty(0, (LAVIGNY, 100_000)))
    assert ledger.commander == CommanderKey(UNKNOWN_COMMANDER, Galaxy.LIVE)
    assert ledger.current.bounties == {LAVIGNY: 100_000}


def test_a_copy_goes_on_alone() -> None:
    ledger = ledger_of()
    ledger.apply(bounty(0, (LAVIGNY, 100_000)))
    copy = ledger.copy()
    copy.apply(CommanderDied(at(1)))
    copy.apply(identified(2, OTHER))
    assert ledger.current.bounties == {LAVIGNY: 100_000}
    assert ledger.commander == FUSION


def test_a_ledger_is_rebuilt_from_what_was_kept() -> None:
    ledger = ledger_of()
    ledger.apply(bounty(0, (LAVIGNY, 100_000)))
    ledger.apply(identified(1, OTHER))
    ledger.apply(bond(1, 5_000, OLKER))
    kept = VoucherLedger.restore(ledger.books, ledger.commander)
    assert kept.books == ledger.books
    assert kept.commander == OTHER
    assert kept.current.combat_bonds == {OLKER: 5_000}


def test_books_leave_out_commanders_without_vouchers() -> None:
    ledger = ledger_of()
    ledger.apply(bounty(0, (LAVIGNY, 100_000)))
    ledger.apply(CommanderDied(at(1)))
    assert ledger.books == {}
