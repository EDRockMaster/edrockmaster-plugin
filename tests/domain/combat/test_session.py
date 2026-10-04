from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.domain.bounty.hunting import (
    CommunityGoalsChanged,
    HuntEnded,
    HuntEndReason,
    HuntingTracker,
    HuntStarted,
    HuntUpdated,
    VouchersUpdated,
)
from edrockmaster.domain.bounty.journal import (
    BountyAwarded,
    CombatBondAwarded,
    CommanderDied,
    CommunityGoal,
    CommunityGoalsUpdated,
    FactionReward,
    GameClosed,
    SiteEntered,
    SiteLeft,
    VoucherKind,
    VouchersRedeemed,
)

T0 = datetime(2026, 10, 3, 21, 0, tzinfo=UTC)
FED = "Federation"
SIRIUS = "Sirius Corporation"


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def bounty(minutes: float, *rewards: tuple[str, int], shared: bool = False) -> BountyAwarded:
    pairs = rewards or ((FED, 100_000),)
    return BountyAwarded(
        at=at(minutes),
        total=sum(amount for _, amount in pairs),
        rewards=tuple(FactionReward(faction, amount) for faction, amount in pairs),
        target="Anaconda",
        victim_faction="Pirates",
        shared=shared,
    )


def bond(minutes: float, amount: int = 50_000, kill: bool = True) -> CombatBondAwarded:
    return CombatBondAwarded(
        at=at(minutes), amount=amount, awarding_faction=FED, victim_faction="Empire", kill=kill
    )


def redeemed(minutes: float, kind: VoucherKind, *paid: tuple[str, int]) -> VouchersRedeemed:
    return VouchersRedeemed(
        at=at(minutes),
        kind=kind,
        amount=sum(amount for _, amount in paid),
        by_faction=tuple(FactionReward(faction, amount) for faction, amount in paid),
    )


def kinds(notifications: Sequence[object]) -> list[type]:
    return [type(notification) for notification in notifications]


# --- lifecycle ----------------------------------------------------------------------------


def test_first_kill_starts_a_session() -> None:
    tracker = HuntingTracker()
    notifications = tracker.handle(bounty(0))
    assert kinds(notifications) == [HuntStarted, HuntUpdated, VouchersUpdated]
    assert notifications[0] == HuntStarted(at(0))
    assert tracker.session is not None


def test_combat_bond_also_starts_a_session() -> None:
    tracker = HuntingTracker()
    assert kinds(tracker.handle(bond(0)))[0] is HuntStarted


@pytest.mark.parametrize(
    ("fact", "reason"),
    [(CommanderDied(at(5)), HuntEndReason.DIED), (GameClosed(at(5)), HuntEndReason.GAME_CLOSED)],
)
def test_death_or_game_exit_ends_the_session(
    fact: CommanderDied | GameClosed, reason: HuntEndReason
) -> None:
    tracker = HuntingTracker()
    tracker.handle(bounty(0))
    ended = tracker.handle(fact)[0]
    assert isinstance(ended, HuntEnded)
    assert ended.reason is reason
    assert ended.stats.kills == 1
    assert tracker.session is None


def test_ending_without_a_session_notifies_nothing_about_it() -> None:
    assert HuntingTracker().handle(GameClosed(at(0))) == []


def test_manual_reset() -> None:
    tracker = HuntingTracker()
    assert tracker.reset(at(0)) is None
    tracker.handle(bounty(0))
    ended = tracker.reset(at(3))
    assert ended is not None
    assert ended.reason is HuntEndReason.MANUAL
    assert kinds(tracker.handle(bounty(4)))[0] is HuntStarted


# --- statistics ---------------------------------------------------------------------------


def test_kills_and_credits() -> None:
    tracker = HuntingTracker()
    tracker.handle(bounty(0, (FED, 100_000), (SIRIUS, 20_000)))
    tracker.handle(bond(10, 50_000))
    updated = tracker.handle(bond(20, 400_000, kill=False))[0]
    assert isinstance(updated, HuntUpdated)
    stats = updated.stats
    assert stats.kills == 2
    assert stats.bounty_credits == 120_000
    assert stats.bond_credits == 450_000
    assert stats.credits == 570_000
    assert stats.active_duration == timedelta(minutes=20)
    assert stats.credits_per_hour == pytest.approx(1_710_000)
    assert stats.kills_per_hour == pytest.approx(6)


def test_shared_kills_are_counted_apart() -> None:
    tracker = HuntingTracker()
    tracker.handle(bounty(0))
    updated = tracker.handle(bounty(1, shared=True))[0]
    assert isinstance(updated, HuntUpdated)
    assert (updated.stats.kills, updated.stats.shared_kills) == (2, 1)


def active(notification: object) -> timedelta:
    assert isinstance(notification, HuntUpdated | HuntEnded)
    return notification.stats.active_duration


def test_time_on_site_counts_from_the_arrival_before_the_first_reward() -> None:
    tracker = HuntingTracker()
    assert tracker.handle(SiteEntered(at(0))) == []
    assert active(tracker.handle(bounty(5))[1]) == timedelta(minutes=5)


def test_searching_for_targets_counts_however_long_it_takes() -> None:
    tracker = HuntingTracker()
    tracker.handle(SiteEntered(at(0)))
    tracker.handle(bounty(1))
    assert active(tracker.handle(bounty(31))[0]) == timedelta(minutes=31)


def test_time_off_site_is_not_counted() -> None:
    tracker = HuntingTracker()
    tracker.handle(SiteEntered(at(0)))
    tracker.handle(bounty(10))
    [left] = tracker.handle(SiteLeft(at(12)))
    assert active(left) == timedelta(minutes=12)
    tracker.handle(SiteEntered(at(30)))
    assert active(tracker.handle(bounty(40))[0]) == timedelta(minutes=22)


def test_sites_without_a_session_notify_nothing() -> None:
    tracker = HuntingTracker()
    assert tracker.handle(SiteEntered(at(0))) == []
    assert tracker.handle(SiteLeft(at(5))) == []


def test_an_earlier_site_does_not_count_for_a_later_session() -> None:
    tracker = HuntingTracker()
    tracker.handle(SiteEntered(at(0)))
    tracker.handle(SiteLeft(at(5)))
    tracker.handle(SiteEntered(at(60)))
    assert active(tracker.handle(bounty(70))[1]) == timedelta(minutes=10)


def test_without_a_known_site_time_counts_from_the_first_reward() -> None:
    tracker = HuntingTracker()
    tracker.handle(bounty(0))
    assert active(tracker.handle(bounty(10))[0]) == timedelta(minutes=10)


@pytest.mark.parametrize("end", [GameClosed(at(20)), CommanderDied(at(20))])
def test_the_end_of_a_session_closes_the_site(end: GameClosed | CommanderDied) -> None:
    tracker = HuntingTracker()
    tracker.handle(SiteEntered(at(0)))
    tracker.handle(bounty(5))
    assert active(tracker.handle(end)[0]) == timedelta(minutes=20)


def test_a_reset_closes_the_site() -> None:
    tracker = HuntingTracker()
    tracker.handle(SiteEntered(at(0)))
    tracker.handle(bounty(5))
    ended = tracker.reset(at(8))
    assert ended is not None
    assert ended.stats.active_duration == timedelta(minutes=8)


def test_rates_are_zero_without_active_time() -> None:
    tracker = HuntingTracker()
    updated = tracker.handle(bounty(0))[1]
    assert isinstance(updated, HuntUpdated)
    assert (updated.stats.credits_per_hour, updated.stats.kills_per_hour) == (0.0, 0.0)


# --- vouchers -----------------------------------------------------------------------------


def test_vouchers_accumulate_per_faction() -> None:
    tracker = HuntingTracker()
    tracker.handle(bounty(0, (FED, 100_000), (SIRIUS, 20_000)))
    tracker.handle(bounty(1, (FED, 50_000)))
    vouchers = tracker.handle(bond(2, 30_000))[-1]
    assert isinstance(vouchers, VouchersUpdated)
    assert vouchers.vouchers.bounties == {FED: 150_000, SIRIUS: 20_000}
    assert vouchers.vouchers.combat_bonds == {FED: 30_000}
    assert vouchers.vouchers.total == 200_000


def test_redeeming_removes_the_vouchers_paid() -> None:
    tracker = HuntingTracker()
    tracker.handle(bounty(0, (FED, 100_000), (SIRIUS, 20_000)))
    tracker.handle(bond(1, 30_000))
    [updated] = tracker.handle(redeemed(5, VoucherKind.BOUNTY, (FED, 100_000)))
    assert isinstance(updated, VouchersUpdated)
    assert updated.vouchers.bounties == {SIRIUS: 20_000}
    [updated] = tracker.handle(redeemed(6, VoucherKind.COMBAT_BOND, (FED, 30_000)))
    assert isinstance(updated, VouchersUpdated)
    assert updated.vouchers.combat_bonds == {}


def test_redeeming_vouchers_earned_before_edmc_started_never_goes_negative() -> None:
    tracker = HuntingTracker()
    tracker.handle(bounty(0, (FED, 10_000)))
    [updated] = tracker.handle(redeemed(1, VoucherKind.BOUNTY, (FED, 90_000), (SIRIUS, 5_000)))
    assert isinstance(updated, VouchersUpdated)
    assert updated.vouchers.bounties == {}


def test_redeeming_does_not_touch_the_session() -> None:
    tracker = HuntingTracker()
    tracker.handle(bounty(0))
    tracker.handle(redeemed(1, VoucherKind.BOUNTY, (FED, 100_000)))
    assert tracker.session is not None
    assert tracker.session.stats.bounty_credits == 100_000


def test_death_loses_the_unredeemed_vouchers() -> None:
    tracker = HuntingTracker()
    tracker.handle(bounty(0))
    notifications = tracker.handle(CommanderDied(at(1)))
    assert kinds(notifications) == [HuntEnded, VouchersUpdated]
    assert tracker.vouchers.total == 0


def test_death_without_vouchers_notifies_no_voucher_change() -> None:
    tracker = HuntingTracker()
    assert tracker.handle(CommanderDied(at(1))) == []


# --- community goals ----------------------------------------------------------------------


def test_community_goals_are_kept_and_notified() -> None:
    goal = CommunityGoal(
        cgid=812,
        title="Defend the Sirius Gate",
        system="Sirius",
        expiry=None,
        complete=False,
        contribution=25_000_000,
        percentile_band=25,
        tier_reached="Tier 4",
        top_tier="Tier 8",
    )
    tracker = HuntingTracker()
    assert tracker.handle(CommunityGoalsUpdated(at(0), (goal,))) == [CommunityGoalsChanged((goal,))]
    assert tracker.community_goals == (goal,)
    assert tracker.session is None


def test_a_second_arrival_without_leaving_keeps_the_first() -> None:
    tracker = HuntingTracker()
    tracker.handle(SiteEntered(at(0)))
    tracker.handle(bounty(5))
    tracker.handle(SiteEntered(at(7)))
    assert active(tracker.handle(bounty(10))[0]) == timedelta(minutes=10)


def test_a_reward_off_site_restarts_the_site_clock() -> None:
    # The journal did not tell the new site: time counts from that reward
    tracker = HuntingTracker()
    tracker.handle(SiteEntered(at(0)))
    tracker.handle(bounty(5))
    tracker.handle(SiteLeft(at(6)))
    tracker.handle(bounty(10))
    assert active(tracker.handle(bounty(12))[0]) == timedelta(minutes=8)
