from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.domain.combat.journal import (
    BountyAwarded,
    CombatBondAwarded,
    CommanderDied,
    CommunityGoal,
    CommunityGoalsUpdated,
    CrimeCommitted,
    DestinationDropped,
    Embarked,
    FactionReward,
    GameClosed,
    GameLoaded,
    MiningSeen,
    NormalSpaceEntered,
    OnFootArrived,
    SettlementApproached,
    SiteLeft,
    VoucherKind,
    VouchersRedeemed,
)
from edrockmaster.domain.combat.session import (
    CombatEnded,
    CombatEndReason,
    CombatStarted,
    CombatStats,
    CombatTracker,
    CombatUpdated,
    CommunityGoalsChanged,
    Tally,
    VouchersUpdated,
)
from edrockmaster.domain.combat.sites import SiteType

T0 = datetime(2026, 10, 3, 21, 0, tzinfo=UTC)
FED = "Federation"
SIRIUS = "Sirius Corporation"
CZ = SiteType.CONFLICT_ZONE_HIGH
RES = SiteType.RES_HAZARDOUS
GROUND = SiteType.GROUND_CONFLICT_ZONE
UNNAMED_CZ = SiteType.CONFLICT_ZONE_UNKNOWN


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


def arrive(tracker: CombatTracker, minutes: float, site: SiteType | None = CZ) -> None:
    """Supercruise ends at a chosen destination, as the journal writes it."""
    assert tracker.handle(DestinationDropped(at(minutes), site)) == []
    assert tracker.handle(NormalSpaceEntered(at(minutes))) == []


def stats_of(notifications: Sequence[object]) -> CombatStats:
    [stats] = [n.stats for n in notifications if isinstance(n, CombatUpdated | CombatEnded)]
    return stats


def on_site(tracker: CombatTracker) -> CombatTracker:
    arrive(tracker, 0)
    return tracker


# --- lifecycle ----------------------------------------------------------------------------


def test_first_reward_starts_a_session() -> None:
    tracker = on_site(CombatTracker())
    notifications = tracker.handle(bounty(1))
    assert kinds(notifications) == [CombatStarted, CombatUpdated, VouchersUpdated]
    assert notifications[0] == CombatStarted(at(1))
    assert tracker.session is not None


def test_combat_bond_also_starts_a_session() -> None:
    assert kinds(on_site(CombatTracker()).handle(bond(1)))[0] is CombatStarted


@pytest.mark.parametrize(
    ("fact", "reason"),
    [
        (CommanderDied(at(5)), CombatEndReason.DIED),
        (GameClosed(at(5)), CombatEndReason.GAME_CLOSED),
    ],
)
def test_death_or_game_exit_ends_the_session(
    fact: CommanderDied | GameClosed, reason: CombatEndReason
) -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bounty(1))
    ended = tracker.handle(fact)[0]
    assert isinstance(ended, CombatEnded)
    assert ended.reason is reason
    assert ended.stats.kills == 1
    assert ended.stats.active_duration == timedelta(minutes=5)
    assert tracker.session is None


def test_ending_without_a_session_notifies_nothing_about_it() -> None:
    assert CombatTracker().handle(GameClosed(at(0))) == []


def test_manual_reset() -> None:
    tracker = on_site(CombatTracker())
    assert tracker.reset(at(0)) is None
    tracker.handle(bounty(1))
    ended = tracker.reset(at(3))
    assert ended is not None
    assert ended.reason is CombatEndReason.MANUAL
    assert ended.stats.active_duration == timedelta(minutes=3)
    # Still on the site: the next segment starts at the reset
    assert stats_of(tracker.handle(bounty(5))).active_duration == timedelta(minutes=2)


def test_another_activity_never_ends_the_session() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bounty(1))
    tracker.handle(SiteLeft(at(2)))
    tracker.handle(NormalSpaceEntered(at(10)))
    assert tracker.handle(MiningSeen(at(11))) == []
    assert tracker.session is not None


# --- segments -----------------------------------------------------------------------------


def test_a_segment_starts_on_arrival_at_the_combat_site() -> None:
    tracker = on_site(CombatTracker())
    stats = stats_of(tracker.handle(bond(5)))
    assert stats.current is not None
    assert stats.current.site is CZ
    assert stats.current.started_at == at(0)
    assert stats.current.duration == timedelta(minutes=5)
    assert stats.active_duration == timedelta(minutes=5)


def test_a_segment_has_its_own_rates() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bond(10, 100_000))
    current = stats_of(tracker.handle(bond(30, 200_000))).current
    assert current is not None
    assert (current.kills_per_hour, current.credits_per_hour) == (4.0, 600_000.0)


def test_searching_for_targets_counts_however_long_it_takes() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bounty(1))
    assert stats_of(tracker.handle(bounty(31))).active_duration == timedelta(minutes=31)


def test_leaving_the_site_closes_its_segment() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bond(5))
    stats = stats_of(tracker.handle(SiteLeft(at(12))))
    assert stats.current is None
    [segment] = stats.segments
    assert (segment.site, segment.duration, segment.tally.kills) == (CZ, timedelta(minutes=12), 1)


def test_time_between_sites_is_not_counted() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bond(10))
    tracker.handle(SiteLeft(at(12)))
    arrive(tracker, 30)
    assert stats_of(tracker.handle(bond(40))).active_duration == timedelta(minutes=22)


def test_a_site_without_reward_is_not_counted() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bond(10))
    tracker.handle(SiteLeft(at(12)))
    arrive(tracker, 20, RES)
    assert tracker.handle(SiteLeft(at(25))) == []
    assert tracker.session is not None
    assert tracker.session.stats.active_duration == timedelta(minutes=12)


def test_a_combat_site_visited_without_a_session_starts_nothing() -> None:
    tracker = on_site(CombatTracker())
    assert tracker.handle(SiteLeft(at(5))) == []
    assert tracker.session is None


def test_segments_of_a_site_type_are_averaged_by_time() -> None:
    # The two high-intensity conflict zones of 3 October 2026 (game 4.4.1.1)
    tracker = CombatTracker()
    arrive(tracker, 0)
    for minute in range(16):
        tracker.handle(bond(1 + minute, 587_256 // 16 + (1 if minute < 587_256 % 16 else 0)))
    tracker.handle(SiteLeft(T0 + timedelta(minutes=20, seconds=11)))
    arrive(tracker, 21)
    for minute in range(13):
        tracker.handle(bond(22 + minute, 566_000 // 13 + (1 if minute < 566_000 % 13 else 0)))
    stats = stats_of(tracker.handle(SiteLeft(T0 + timedelta(minutes=50, seconds=8))))
    [average] = stats.by_site()
    assert average.site is CZ
    assert average.duration == timedelta(minutes=49, seconds=19)
    assert (average.tally.kills, average.tally.credits) == (29, 1_153_256)
    assert round(average.kills_per_hour, 1) == 35.3
    assert round(average.credits_per_hour) == 1_403_083


def test_site_types_are_averaged_apart_in_order_of_first_visit() -> None:
    tracker = CombatTracker()
    arrive(tracker, 0, RES)
    tracker.handle(bounty(10))
    tracker.handle(SiteLeft(at(10)))
    arrive(tracker, 20, CZ)
    tracker.handle(bond(50, 300_000))
    stats = stats_of(tracker.handle(SiteLeft(at(50))))
    res, cz = stats.by_site()
    assert (res.site, cz.site) == (RES, CZ)
    assert res.credits_per_hour == pytest.approx(600_000)
    assert cz.credits_per_hour == pytest.approx(600_000)
    assert stats.credits_per_hour == pytest.approx(400_000 / (40 / 60))


def test_the_current_segment_counts_in_its_site_average() -> None:
    tracker = on_site(CombatTracker())
    [average] = stats_of(tracker.handle(bond(30, 100_000))).by_site()
    assert average.credits_per_hour == pytest.approx(200_000)


def test_kills_and_credits() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bounty(0, (FED, 100_000), (SIRIUS, 20_000)))
    tracker.handle(bond(10, 50_000))
    stats = stats_of(tracker.handle(bond(20, 400_000, kill=False)))
    assert stats.kills == 2
    assert stats.bounty_credits == 120_000
    assert stats.bond_credits == 450_000
    assert stats.credits == 570_000
    assert stats.credits_per_hour == pytest.approx(1_710_000)
    assert stats.kills_per_hour == pytest.approx(6)


def test_shared_kills_are_counted_apart() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bounty(0))
    stats = stats_of(tracker.handle(bounty(1, shared=True)))
    assert (stats.kills, stats.shared_kills) == (2, 1)


def test_rates_are_zero_without_time() -> None:
    tracker = CombatTracker()
    stats = stats_of(tracker.handle(bounty(0)))
    assert (stats.credits_per_hour, stats.kills_per_hour) == (0.0, 0.0)
    [average] = stats.by_site()
    assert (average.credits_per_hour, average.kills_per_hour) == (0.0, 0.0)


@pytest.mark.parametrize("end", [GameClosed(at(20)), CommanderDied(at(20))])
def test_the_end_of_a_session_closes_the_segment(end: GameClosed | CommanderDied) -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bounty(5))
    stats = stats_of(tracker.handle(end))
    assert (stats.current, stats.active_duration) == (None, timedelta(minutes=20))


def test_a_second_drop_while_on_site_does_not_move_the_segment() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bounty(5))
    arrive(tracker, 7, RES)
    stats = stats_of(tracker.handle(bounty(10)))
    assert stats.current is not None
    assert (stats.current.site, stats.active_duration) == (CZ, timedelta(minutes=10))


# --- unknown site and miscellaneous -------------------------------------------------------


def test_without_a_known_arrival_a_reward_opens_an_unknown_segment() -> None:
    tracker = CombatTracker()  # EDMC started on the site
    tracker.handle(bounty(5))
    stats = stats_of(tracker.handle(bounty(15)))
    assert stats.current is not None
    assert stats.current.site is SiteType.UNKNOWN
    assert stats.active_duration == timedelta(minutes=10)


def test_game_loaded_in_space_is_an_unknown_site() -> None:
    tracker = CombatTracker()
    tracker.handle(GameLoaded(at(0), docked=False))
    stats = stats_of(tracker.handle(bounty(5)))
    assert stats.current is not None
    assert stats.current.site is SiteType.UNKNOWN


@pytest.mark.parametrize(
    "facts",
    [
        # a ring, a planet, deep space: supercruise ends without a destination
        [NormalSpaceEntered(at(0))],
        # a station, a signal source: a destination that is not a combat site
        [DestinationDropped(at(0), None), NormalSpaceEntered(at(0))],
        # undocking, after loading the game docked
        [GameLoaded(at(0), docked=True), NormalSpaceEntered(at(1))],
        # EDMC started on a site where the commander mines
        [MiningSeen(at(1))],
        # supercruise, before any arrival
        [SiteLeft(at(0))],
    ],
)
def test_kills_off_combat_sites_are_miscellaneous(facts: list[object]) -> None:
    tracker = CombatTracker()
    for fact in facts:
        tracker.handle(fact)  # type: ignore[arg-type]
    stats = stats_of(tracker.handle(bounty(5)))
    assert stats.segments == ()
    assert stats.miscellaneous == Tally(kills=1, bounty_credits=100_000)
    assert (stats.kills, stats.credits) == (1, 100_000)
    assert (stats.active_duration, stats.credits_per_hour) == (timedelta(0), 0.0)


def test_a_drop_counts_only_for_the_arrival_that_follows_it() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(SiteLeft(at(1)))
    tracker.handle(NormalSpaceEntered(at(5)))  # a ring, no destination
    assert stats_of(tracker.handle(bounty(6))).segments == ()


def test_miscellaneous_kills_and_segments_add_up() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bond(10, 200_000))
    tracker.handle(SiteLeft(at(10)))
    tracker.handle(NormalSpaceEntered(at(20)))
    tracker.handle(MiningSeen(at(21)))
    stats = stats_of(tracker.handle(bounty(30)))
    assert (stats.kills, stats.credits) == (2, 300_000)
    assert stats.credits_per_hour == pytest.approx(1_200_000)


# --- conflict zones the journal does not name, ground conflict zones (ADR 0015) ------------


def test_a_bond_after_an_unnamed_drop_opens_a_conflict_zone_from_the_arrival() -> None:
    tracker = CombatTracker()
    tracker.handle(NormalSpaceEntered(at(0)))  # no SupercruiseDestinationDrop
    stats = stats_of(tracker.handle(bond(2)))
    assert stats.current is not None
    assert (stats.current.site, stats.current.started_at) == (UNNAMED_CZ, at(0))
    assert stats.miscellaneous == Tally()


def test_a_conflict_zone_of_unknown_intensity_is_averaged_apart() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bond(10))
    tracker.handle(SiteLeft(at(10)))
    tracker.handle(NormalSpaceEntered(at(20)))
    tracker.handle(bond(30))
    stats = stats_of(tracker.handle(SiteLeft(at(30))))
    assert [average.site for average in stats.by_site()] == [CZ, UNNAMED_CZ]


def test_a_bond_without_a_known_arrival_opens_a_conflict_zone_from_the_bond() -> None:
    tracker = CombatTracker()  # EDMC started on the site
    tracker.handle(bond(5))
    stats = stats_of(tracker.handle(bond(15)))
    assert stats.current is not None
    assert (stats.current.site, stats.current.started_at) == (UNNAMED_CZ, at(5))


def test_a_bond_while_mining_still_opens_a_conflict_zone() -> None:
    tracker = CombatTracker()
    tracker.handle(NormalSpaceEntered(at(0)))
    tracker.handle(MiningSeen(at(1)))
    assert stats_of(tracker.handle(bond(2))).miscellaneous == Tally()


@pytest.mark.parametrize(
    "facts",
    [
        # after an unnamed drop: a pirate can be shot down anywhere
        [NormalSpaceEntered(at(0))],
        # on foot, outside any conflict zone
        [OnFootArrived(at(0), dropship=False)],
    ],
)
def test_a_bounty_never_tells_the_place(facts: list[object]) -> None:
    tracker = CombatTracker()
    for fact in facts:
        tracker.handle(fact)  # type: ignore[arg-type]
    stats = stats_of(tracker.handle(bounty(5)))
    assert (stats.segments, stats.miscellaneous.kills) == ((), 1)


def test_a_capital_ship_bond_does_not_tell_the_place() -> None:
    tracker = CombatTracker()
    tracker.handle(NormalSpaceEntered(at(0)))
    assert stats_of(tracker.handle(bond(5, kill=False))).segments == ()


def test_the_dropship_opens_a_ground_conflict_zone_from_the_deploy() -> None:
    tracker = CombatTracker()
    tracker.handle(SettlementApproached(at(0), "Parra Prospecting Complex"))
    tracker.handle(NormalSpaceEntered(at(0)))
    tracker.handle(OnFootArrived(at(1), dropship=True))
    stats = stats_of(tracker.handle(bond(5)))
    assert stats.current is not None
    assert (stats.current.site, stats.current.started_at) == (GROUND, at(1))
    assert stats.current.settlement == "Parra Prospecting Complex"


def test_a_redeploy_continues_the_ground_segment() -> None:
    tracker = CombatTracker()
    tracker.handle(OnFootArrived(at(0), dropship=True))
    tracker.handle(bond(5))
    tracker.handle(OnFootArrived(at(9), dropship=True))  # back after a defeat on foot
    stats = stats_of(tracker.handle(bond(10)))
    assert len(stats.segments) == 1
    assert stats.active_duration == timedelta(minutes=10)


@pytest.mark.parametrize(
    "departure",
    [SiteLeft(at(15)), Embarked(at(15), on_station=False), CommanderDied(at(15))],
)
def test_leaving_a_ground_conflict_zone_closes_its_segment(departure: object) -> None:
    tracker = CombatTracker()
    tracker.handle(OnFootArrived(at(0), dropship=True))
    tracker.handle(bond(5))
    stats = stats_of(tracker.handle(departure))  # type: ignore[arg-type]
    assert stats.current is None
    assert stats.active_duration == timedelta(minutes=15)


def test_a_bond_on_foot_opens_a_ground_conflict_zone_from_the_disembark() -> None:
    tracker = CombatTracker()
    tracker.handle(SettlementApproached(at(0), "Pak's Habitat"))
    tracker.handle(NormalSpaceEntered(at(0)))
    tracker.handle(OnFootArrived(at(3), dropship=False))  # own ship, then on foot
    stats = stats_of(tracker.handle(bond(8)))
    assert stats.current is not None
    assert (stats.current.site, stats.current.started_at) == (GROUND, at(3))
    assert stats.current.settlement == "Pak's Habitat"


def test_a_bond_on_foot_without_a_known_arrival_opens_a_ground_conflict_zone() -> None:
    tracker = CombatTracker()
    tracker.handle(GameLoaded(at(0), docked=False, on_foot=True))
    stats = stats_of(tracker.handle(bond(5)))
    assert stats.current is not None
    assert (stats.current.site, stats.current.started_at) == (GROUND, at(5))


def test_back_in_the_ship_on_a_planet_a_bond_opens_a_space_conflict_zone() -> None:
    tracker = CombatTracker()
    tracker.handle(OnFootArrived(at(0), dropship=False))
    tracker.handle(Embarked(at(4), on_station=False))
    stats = stats_of(tracker.handle(bond(6)))
    assert stats.current is not None
    assert (stats.current.site, stats.current.started_at) == (UNNAMED_CZ, at(4))


def test_embarking_at_a_station_leaves_no_place_to_fight() -> None:
    tracker = CombatTracker()
    tracker.handle(Embarked(at(0), on_station=True))
    assert stats_of(tracker.handle(bond(5))).segments == ()


def test_only_ground_segments_carry_the_settlement() -> None:
    tracker = CombatTracker()
    tracker.handle(SettlementApproached(at(0), "Parra Prospecting Complex"))
    tracker.handle(NormalSpaceEntered(at(0)))
    stats = stats_of(tracker.handle(bond(2)))  # by ship, near the settlement
    assert stats.current is not None
    assert stats.current.settlement is None


def test_the_settlement_is_forgotten_on_departure() -> None:
    tracker = CombatTracker()
    tracker.handle(SettlementApproached(at(0), "Parra Prospecting Complex"))
    tracker.handle(SiteLeft(at(1)))
    tracker.handle(OnFootArrived(at(5), dropship=True))
    stats = stats_of(tracker.handle(bond(6)))
    assert stats.current is not None
    assert stats.current.settlement is None


# --- crimes -------------------------------------------------------------------------------


def test_crimes_are_counted_by_kind_during_a_session() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bounty(1))
    tracker.handle(CrimeCommitted(at(2), "recklessWeaponsDischarge", fine=100, bounty=0))
    stats = stats_of(tracker.handle(CrimeCommitted(at(3), "assault", fine=0, bounty=400)))
    crimes = stats.crimes
    assert (crimes.count, crimes.fines, crimes.bounties) == (2, 100, 400)
    assert crimes.by_kind == {"recklessWeaponsDischarge": 1, "assault": 1}
    assert stats.credits == 100_000  # never deducted from what was earned


def test_crimes_without_a_session_are_ignored() -> None:
    tracker = CombatTracker()
    assert tracker.handle(CrimeCommitted(at(0), "assault", fine=100, bounty=0)) == []
    assert tracker.session is None


# --- vouchers -----------------------------------------------------------------------------


def test_vouchers_accumulate_per_faction() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bounty(0, (FED, 100_000), (SIRIUS, 20_000)))
    tracker.handle(bounty(1, (FED, 50_000)))
    vouchers = tracker.handle(bond(2, 30_000))[-1]
    assert isinstance(vouchers, VouchersUpdated)
    assert vouchers.vouchers.bounties == {FED: 150_000, SIRIUS: 20_000}
    assert vouchers.vouchers.combat_bonds == {FED: 30_000}
    assert vouchers.vouchers.total == 200_000


def test_redeeming_removes_the_vouchers_paid() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bounty(0, (FED, 100_000), (SIRIUS, 20_000)))
    tracker.handle(bond(1, 30_000))
    [updated] = tracker.handle(redeemed(5, VoucherKind.BOUNTY, (FED, 100_000)))
    assert isinstance(updated, VouchersUpdated)
    assert updated.vouchers.bounties == {SIRIUS: 20_000}
    [updated] = tracker.handle(redeemed(6, VoucherKind.COMBAT_BOND, (FED, 30_000)))
    assert isinstance(updated, VouchersUpdated)
    assert updated.vouchers.combat_bonds == {}


def test_redeeming_vouchers_earned_before_edmc_started_never_goes_negative() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bounty(0, (FED, 10_000)))
    [updated] = tracker.handle(redeemed(1, VoucherKind.BOUNTY, (FED, 90_000), (SIRIUS, 5_000)))
    assert isinstance(updated, VouchersUpdated)
    assert updated.vouchers.bounties == {}


def test_redeeming_does_not_touch_the_session() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bounty(0))
    tracker.handle(redeemed(1, VoucherKind.BOUNTY, (FED, 100_000)))
    assert tracker.session is not None
    assert tracker.session.stats.bounty_credits == 100_000


def test_miscellaneous_kills_earn_vouchers_too() -> None:
    tracker = CombatTracker()
    tracker.handle(NormalSpaceEntered(at(0)))
    assert tracker.handle(bounty(1))[-1] == VouchersUpdated(tracker.vouchers)
    assert tracker.vouchers.total == 100_000


def test_death_loses_the_unredeemed_vouchers() -> None:
    tracker = on_site(CombatTracker())
    tracker.handle(bounty(0))
    notifications = tracker.handle(CommanderDied(at(1)))
    assert kinds(notifications) == [CombatEnded, VouchersUpdated]
    assert tracker.vouchers.total == 0


def test_death_without_vouchers_notifies_no_voucher_change() -> None:
    assert CombatTracker().handle(CommanderDied(at(1))) == []


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
    tracker = CombatTracker()
    assert tracker.handle(CommunityGoalsUpdated(at(0), (goal,))) == [CommunityGoalsChanged((goal,))]
    assert tracker.community_goals == (goal,)
    assert tracker.session is None
