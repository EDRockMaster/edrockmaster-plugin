"""Replays of real play sessions, recorded in game (tests/fixtures/, sanitised).

Each fixture was produced by the journal recorder, then by
scripts/sanitise_recording.py; the expected figures were checked by hand
against the raw journal.

The two fixtures of 3 October 2026 were sanitised before the sanitiser kept
``SupercruiseDestinationDrop``: the arrivals on combat sites are not named. Their
conflict zones are told by the combat bonds, with an unknown intensity (ADR 0015);
their bounties at a resource site are miscellaneous, without any rate.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from edrockmaster.application.activity import Activity
from edrockmaster.application.companion import Companion, Notification
from edrockmaster.application.settings import DEFAULT_SETTINGS
from edrockmaster.domain.combat.session import (
    CombatEnded,
    CombatEndReason,
    CombatStats,
    CommunityGoalsChanged,
    Tally,
    VouchersUpdated,
)
from edrockmaster.domain.combat.sites import SiteType
from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.mining.session import EndReason, SessionEnded
from edrockmaster.domain.trade.journal import Market
from edrockmaster.domain.trade.session import (
    GoodsTally,
    TradeEnded,
    TradeEndReason,
    TradeStats,
    TransferKind,
    TransferStats,
)
from edrockmaster.ui.presenter import ActivityPresenter
from tests.fakes import FakeNotifier, FakeRecorder, FakeSettingsStore, FixedClock

FIXTURES = Path(__file__).parent / "fixtures"


class Replay:
    def __init__(self, fixture: str) -> None:
        self.notifier = FakeNotifier()
        self.companion = Companion(
            FakeSettingsStore(DEFAULT_SETTINGS),
            self.notifier,
            FakeRecorder(),
            FixedClock(datetime(2026, 10, 3, 13, 0, tzinfo=UTC)),
        )
        self.presenter = ActivityPresenter()
        self.notifications: list[Notification] = []
        self.panel_switches: list[tuple[str, Activity]] = []
        for line in (FIXTURES / fixture).read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            produced = self.companion.handle_journal_entry(record["entry"], record["is_beta"])
            shown = self.presenter.current
            self.presenter.apply(produced)
            if self.presenter.current is not shown:
                self.panel_switches.append((record["entry"]["timestamp"], self.presenter.current))
            self.notifications += produced

    def lines(self) -> list[tuple[str, str]]:
        return [(line.label, line.value) for line in self.presenter.render().lines]


@pytest.fixture(scope="module")
def conflict_zone() -> Replay:
    """40 minutes in a war conflict zone at Redonesses during a community goal (4.4.1.1),
    then a visit to the community goal's tab at the station."""
    return Replay("redonesses-conflict-zone-2026-10-03.jsonl")


def test_conflict_zone_kills_and_combat_bonds(conflict_zone: Replay) -> None:
    stats = conflict_zone.companion.combat.current_stats
    assert stats is not None
    assert (stats.kills, stats.shared_kills) == (6, 0)
    assert (stats.bounty_credits, stats.bond_credits) == (0, 224_467)
    # The drop in the zone is not named in this fixture: the bonds tell it, from the
    # arrival at 11:38:45 to the supercruise at 12:04:53
    assert stats.miscellaneous == Tally()
    [zone] = stats.segments
    assert (zone.site, zone.duration) == (
        SiteType.CONFLICT_ZONE_UNKNOWN,
        timedelta(minutes=26, seconds=8),
    )


def test_conflict_zone_redemption_includes_bonds_earned_before_edmc(
    conflict_zone: Replay,
) -> None:
    # 855,491 CR redeemed, more than the 224,467 CR seen: the rest predates EDMC's start
    assert conflict_zone.companion.combat.vouchers.total == 0


def test_conflict_zone_community_goal(conflict_zone: Replay) -> None:
    [goal] = conflict_zone.companion.combat.community_goals
    assert (goal.cgid, goal.contribution, goal.percentile_band) == (860, 2_408_404, 50)
    # The game localises the tier names in the updates written from the station's tab
    # ("Tier 5" before, "Niveau 5" after): they are shown as the journal gives them
    assert (goal.tier_reached, goal.top_tier, goal.complete) == (None, "Niveau 5", False)
    assert goal.system == "Redonesses"


def test_combat_bonds_redeemed_count_towards_the_community_goal(conflict_zone: Replay) -> None:
    # The goal only updates when its tab is opened: 1,552,913 before, 2,408,404 after the
    # redemption of 855,491 CR of combat bonds, and the commander moves from top 75 % to 50 %
    contributions = [
        (goal.contribution, goal.percentile_band)
        for notification in conflict_zone.notifications
        if isinstance(notification, CommunityGoalsChanged)
        for goal in notification.goals
    ]
    assert contributions[0] == (1_552_913, 75)
    assert contributions[-1] == (2_408_404, 50)
    assert contributions[-1][0] - contributions[0][0] == 855_491


def test_conflict_zone_is_not_mining(conflict_zone: Replay) -> None:
    assert conflict_zone.companion.mining.current_stats is None
    assert conflict_zone.notifier.notified == []


def test_conflict_zone_panel_shows_the_combat(conflict_zone: Replay) -> None:
    assert conflict_zone.presenter.current is Activity.COMBAT
    assert conflict_zone.presenter.render().status == "Combat"
    lines = conflict_zone.lines()
    assert ("Combat bonds", "224,467 CR") in lines
    assert ("Conflict zone, unknown intensity", "13.8 kills/h, 515,358 CR/h") in lines
    assert ("Éliminez les pilotes criminels…", "2,408,404, top 50 %") in lines


def test_conflict_zone_panel_does_not_show_empty_bounties(conflict_zone: Replay) -> None:
    labels = [line.label for line in conflict_zone.presenter.render().lines]
    assert "Bounties" not in labels


@pytest.fixture(scope="module")
def zone_then_bounties() -> Replay:
    """The same day: 40 more minutes in that conflict zone (EDMC started while docked), two
    game restarts, then 17 bounties at a resource site, a crime and a redemption."""
    return Replay("redonesses-conflict-zone-then-bounties-2026-10-03.jsonl")


def ended_sessions(replay: Replay) -> list[CombatStats]:
    return [n.stats for n in replay.notifications if isinstance(n, CombatEnded)]


def test_each_game_exit_ends_its_session(zone_then_bounties: Replay) -> None:
    reasons = [n.reason for n in zone_then_bounties.notifications if isinstance(n, CombatEnded)]
    assert reasons == [CombatEndReason.GAME_CLOSED, CombatEndReason.GAME_CLOSED]
    assert zone_then_bounties.companion.combat.current_stats is None


def test_conflict_zone_figures(zone_then_bounties: Replay) -> None:
    zone = ended_sessions(zone_then_bounties)[0]
    assert (zone.kills, zone.bounty_credits, zone.bond_credits) == (22, 0, 817_256)
    # Two stays, from 12:53:59 and from 13:08:09, each ended by supercruise
    assert [(segment.site, segment.tally.kills, segment.duration) for segment in zone.segments] == [
        (SiteType.CONFLICT_ZONE_UNKNOWN, 8, timedelta(minutes=13, seconds=40)),
        (SiteType.CONFLICT_ZONE_UNKNOWN, 14, timedelta(minutes=16, seconds=36)),
    ]
    assert zone.miscellaneous == Tally()


def test_bounty_figures(zone_then_bounties: Replay) -> None:
    hunt = ended_sessions(zone_then_bounties)[1]
    assert (hunt.kills, hunt.bounty_credits, hunt.bond_credits) == (17, 6_110_097, 0)
    # A bounty does not tell the place: the resource site is not named in this fixture
    assert hunt.miscellaneous.kills == 17


def test_vouchers_peak_then_are_redeemed_exactly(zone_then_bounties: Replay) -> None:
    unredeemed = [
        n.vouchers.total for n in zone_then_bounties.notifications if isinstance(n, VouchersUpdated)
    ]
    # Bonds: 2,397,033 CR redeemed, of which 1,579,777 CR were earned before EDMC started.
    # Bounties: 6,110,097 CR earned and redeemed, per faction, to the credit.
    assert 817_256 in unredeemed
    assert max(unredeemed) == 6_110_097
    assert unredeemed[-1] == 0


def test_community_goal_grows_by_the_bonds_redeemed(zone_then_bounties: Replay) -> None:
    goals = [
        goal
        for n in zone_then_bounties.notifications
        if isinstance(n, CommunityGoalsChanged)
        for goal in n.goals
    ]
    assert (goals[0].contribution, goals[-1].contribution) == (2_408_404, 4_805_437)
    assert goals[-1].contribution - goals[0].contribution == 2_397_033
    assert goals[-1].tier_reached == "Niveau 1"


def test_panel_after_the_bounties(zone_then_bounties: Replay) -> None:
    model = zone_then_bounties.presenter.render()
    assert model.status == "Combat session ended: game closed"
    assert ("Bounties", "6,110,097 CR") in zone_then_bounties.lines()
    assert zone_then_bounties.companion.mining.current_stats is None


@pytest.fixture(scope="module")
def zones_mining_res() -> Replay:
    """3 and 4 October (game 4.4.1.1): two high-intensity conflict zones at Capricorni Sector
    XZ-Y b5, the bonds redeemed, 52 minutes of mining in Iyakajauja 13 B Ring, visits to two
    resource extraction sites and a navigation beacon, then a bounty and a fine in a
    hazardous RES."""
    return Replay("capricorni-iyakajauja-zones-mining-res-2026-10-04.jsonl")


def combat(replay: Replay) -> CombatStats:
    stats = replay.companion.combat.current_stats
    assert stats is not None
    return stats


def test_one_segment_per_combat_site_with_rewards(zones_mining_res: Replay) -> None:
    segments = [(s.site, s.duration, s.tally) for s in combat(zones_mining_res).segments]
    assert segments == [
        # 00:26:32 to 00:46:43, then 00:47:58 to 01:17:06
        (SiteType.CONFLICT_ZONE_HIGH, timedelta(minutes=20, seconds=11), Tally(16, 0, 0, 587_256)),
        (SiteType.CONFLICT_ZONE_HIGH, timedelta(minutes=29, seconds=8), Tally(13, 0, 0, 566_000)),
        # 05:22:40 to 05:28:01; the sites visited without a reward are not counted
        (SiteType.RES_HAZARDOUS, timedelta(minutes=5, seconds=21), Tally(1, 0, 370_130, 0)),
    ]


def test_averages_per_site_type(zones_mining_res: Replay) -> None:
    zones, res = combat(zones_mining_res).by_site()
    assert (zones.site, zones.duration) == (
        SiteType.CONFLICT_ZONE_HIGH,
        timedelta(minutes=49, seconds=19),
    )
    assert (round(zones.kills_per_hour, 1), round(zones.credits_per_hour)) == (35.3, 1_403_083)
    assert (res.site, round(res.credits_per_hour)) == (SiteType.RES_HAZARDOUS, 4_150_991)


def test_mining_time_is_not_combat_time(zones_mining_res: Replay) -> None:
    # 0.2.2 counted every minute in normal space: 1 h 44 min and 664,594 CR/h
    stats = combat(zones_mining_res)
    assert stats.active_duration == timedelta(minutes=54, seconds=40)
    assert stats.miscellaneous == Tally()


def test_the_mining_session_is_untouched(zones_mining_res: Replay) -> None:
    [ended] = [n for n in zones_mining_res.notifications if isinstance(n, SessionEnded)]
    assert ended.reason is EndReason.SUPERCRUISE
    assert ended.stats.total_tons == 115
    assert ended.stats.active_duration == timedelta(minutes=49, seconds=13)


def test_the_panel_only_switches_on_progress(zones_mining_res: Replay) -> None:
    # Leaving the ring no longer brings back the combat: only the next bounty does
    assert zones_mining_res.panel_switches == [
        ("2026-10-04T00:28:11Z", Activity.COMBAT),
        ("2026-10-04T02:27:45Z", Activity.MINING),
        ("2026-10-04T05:25:06Z", Activity.COMBAT),
    ]


def test_the_fine_is_counted_apart(zones_mining_res: Replay) -> None:
    crimes = combat(zones_mining_res).crimes
    assert (crimes.count, crimes.fines, dict(crimes.by_kind)) == (
        1,
        100,
        {"recklessWeaponsDischarge": 1},
    )
    assert combat(zones_mining_res).credits == 1_153_256 + 370_130


def test_panel_after_the_hazardous_res(zones_mining_res: Replay) -> None:
    assert zones_mining_res.presenter.render().status == "Combat"
    lines = zones_mining_res.lines()
    assert ("Conflict zone, high", "35.3 kills/h, 1,403,083 CR/h") in lines
    assert ("RES, hazardous", "11.2 kills/h, 4,150,991 CR/h") in lines
    assert ("Fines", "100 CR") in lines
    # The bonds were redeemed at 01:30: only the bounty of 05:25 is left
    assert ("Unredeemed", "370,130 CR") in lines


@pytest.fixture(scope="module")
def space_and_ground_zones() -> Replay:
    """An evening at Redonesses (4.4.1.1): two named high-intensity conflict zones, one the
    journal does not name (no ``SupercruiseDestinationDrop``), then two ground conflict zones
    reached with the Frontline Solutions dropship (ADR 0015)."""
    return Replay("redonesses-space-and-ground-conflict-zones-2026-10-04.jsonl")


def test_every_conflict_zone_is_a_segment(space_and_ground_zones: Replay) -> None:
    stats = combat(space_and_ground_zones)
    segments = [
        (segment.site, segment.duration, segment.tally.kills, segment.tally.bond_credits)
        for segment in stats.segments
    ]
    assert segments == [
        # 19:08:44 to 19:33:31, 20:14:49 to 20:38:58: SupercruiseDestinationDrop names them
        (SiteType.CONFLICT_ZONE_HIGH, timedelta(minutes=24, seconds=47), 14, 466_790),
        (SiteType.CONFLICT_ZONE_HIGH, timedelta(minutes=24, seconds=9), 18, 789_885),
        # 21:03:11 to 21:18:21: SupercruiseExit near Redonesses A 1, then bonds
        (SiteType.CONFLICT_ZONE_UNKNOWN, timedelta(minutes=15, seconds=10), 10, 480_293),
        # DropshipDeploy at 21:50:10 (then three redeploys), retreat at 22:04:52
        (SiteType.GROUND_CONFLICT_ZONE, timedelta(minutes=14, seconds=42), 9, 244_134),
        # DropshipDeploy at 22:27:17, retreat at 22:43:25
        (SiteType.GROUND_CONFLICT_ZONE, timedelta(minutes=16, seconds=8), 26, 428_711),
    ]
    assert [segment.settlement for segment in stats.segments] == [
        None,
        None,
        None,
        "Parra Prospecting Complex",
        "Pak's Habitat",
    ]


def test_no_conflict_zone_kill_is_miscellaneous(space_and_ground_zones: Replay) -> None:
    # Under ADR 0013 alone: 45 kills and 1,153,138 CR in miscellaneous
    stats = combat(space_and_ground_zones)
    assert stats.miscellaneous == Tally()
    assert (stats.kills, stats.bond_credits) == (77, 2_409_813)
    # 0.2.2 counted every minute in normal space: 2 h 46 min and 869,707 CR/h
    assert stats.active_duration == timedelta(hours=1, minutes=34, seconds=56)
    assert round(stats.credits_per_hour) == 1_523_056


def test_panel_after_the_ground_conflict_zones(space_and_ground_zones: Replay) -> None:
    lines = space_and_ground_zones.lines()
    assert ("Conflict zone, high", "39.2 kills/h, 1,540,882 CR/h") in lines
    assert ("Conflict zone, unknown intensity", "39.6 kills/h, 1,900,060 CR/h") in lines
    assert ("Ground conflict zone", "68.1 kills/h, 1,309,320 CR/h") in lines
    assert "Miscellaneous" not in dict(lines)


@pytest.fixture(scope="module")
def trade_round_trips() -> Replay:
    """Three round trips with a 1,040-ton ship between Amano Terminal and Verne Venture,
    palladium one way, CMM composite the other (4 October 2026, 4.4.1.1, ADR 0014)."""
    return Replay("amano-verne-trade-2026-10-04.jsonl")


def trade(replay: Replay) -> TradeStats:
    stats = replay.companion.trade.current_stats
    assert stats is not None
    return stats


def test_trade_profit_is_the_game_s_own(trade_round_trips: Replay) -> None:
    stats = trade(trade_round_trips)
    # The sum of (SellPrice - AvgPricePaid) x Count over the six sales
    assert stats.profit == 164_316_218
    assert stats.tons_sold == 5_549
    assert stats.started_at == datetime(2026, 10, 4, 14, 24, 33, tzinfo=UTC)
    assert (stats.losses, stats.cargo) == (0, GoodsTally())
    assert (stats.refined, stats.other) == (GoodsTally(), GoodsTally())


def test_trade_routes(trade_round_trips: Replay) -> None:
    routes = [
        (route.commodity.key, route.origin, route.destination, route.tons, route.profit)
        for route in trade(trade_round_trips).routes
    ]
    assert routes == [
        ("palladium", Market(4300769795), Market(4356317443), 2_429, 119_227_018),
        ("cmmcomposite", Market(4356317443), Market(4300769795), 3_120, 45_089_200),
    ]
    origin = trade(trade_round_trips).routes[0].origin
    assert origin is not None
    assert origin.station == "Amano Terminal"


def test_trade_flight_time(trade_round_trips: Replay) -> None:
    stats = trade(trade_round_trips)
    # Six legs, from 14:27:30 to 16:54:54; not the flight to the first market, nor the
    # flight to the carrier after the last sale
    assert stats.flight_time == timedelta(hours=1, minutes=21, seconds=50)
    assert round(stats.profit_per_hour) == 120_476_249


def test_trade_takes_the_panel_at_the_first_purchase(trade_round_trips: Replay) -> None:
    assert trade_round_trips.panel_switches == [("2026-10-04T14:24:33Z", Activity.TRADE)]
    lines = dict(trade_round_trips.lines())
    assert lines["Profit"] == "164,316,218 CR"
    assert lines["Profit per hour"] == "120,476,249 CR"
    assert lines["Palladium to Verne Venture"] == "2,429 t, 119,227,018 CR, 49,085 CR/t"
    assert lines["Composite MMC to Amano Terminal"] == "3,120 t, 45,089,200 CR, 14,452 CR/t"


def test_trade_is_neither_mining_nor_combat(trade_round_trips: Replay) -> None:
    assert trade_round_trips.companion.mining.current_stats is None
    assert trade_round_trips.companion.combat.current_stats is None


@pytest.fixture(scope="module")
def gold_to_carrier() -> Replay:
    """Gold bought at Abraham Site and moved to the player's fleet carrier, in two loads
    (6 October 2026, from the game journal, ADR 0019). A stop at the carrier from 23:30:46
    to 23:32:05 made no transfer: the known game bug, the gold left again on board."""
    return Replay("abraham-site-gold-to-carrier-2026-10-06.jsonl")


def trade_sessions(replay: Replay) -> list[TradeEnded]:
    return [n for n in replay.notifications if isinstance(n, TradeEnded)]


def test_each_deposit_is_counted_once(gold_to_carrier: Replay) -> None:
    gold = Commodity("gold")
    first, second = trade_sessions(gold_to_carrier)
    # 22:47:24, then 00:04:37: two transfers to the carrier, not three
    assert first.stats.transfers == (TransferStats(gold, TransferKind.DEPOSIT, 1_040, 1),)
    assert second.stats.transfers == (TransferStats(gold, TransferKind.DEPOSIT, 1_040, 1),)


def test_gold_deposited_is_not_lost_with_the_ship(gold_to_carrier: Replay) -> None:
    first, _ = trade_sessions(gold_to_carrier)
    # Destroyed at 23:06:45, after the deposit: nothing bought was on board
    assert (first.reason, first.at) == (
        TradeEndReason.DIED,
        datetime(2026, 10, 6, 23, 6, 45, tzinfo=UTC),
    )
    assert (first.stats.losses, first.stats.cargo) == (0, GoodsTally())


def test_flight_time_to_the_carrier(gold_to_carrier: Replay) -> None:
    first, second = trade_sessions(gold_to_carrier)
    # From Abraham Site, 22:33:15 to 22:40:37
    assert first.stats.flight_time == timedelta(minutes=7, seconds=22)
    # Three legs before the deposit of 00:04:37, the stop without transfer included:
    # 23:18:56-23:30:46, 23:32:05-23:42:26, 23:52:49-00:02:42
    assert second.stats.flight_time == timedelta(minutes=32, seconds=4)
    assert second.reason is TradeEndReason.GAME_CLOSED
    assert (second.stats.profit, second.stats.tons_sold) == (0, 0)


def test_panel_after_the_deposit(gold_to_carrier: Replay) -> None:
    lines = dict(gold_to_carrier.lines())
    assert lines["Deposited: Or"] == "1,040 t (1 transfer)"
