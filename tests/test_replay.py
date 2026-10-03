"""Replays of real play sessions, recorded in game (tests/fixtures/, sanitised).

Each fixture was produced by the journal recorder, then by
scripts/sanitise_recording.py; the expected figures were checked by hand
against the raw journal.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from edrockmaster.application.activity import Activity
from edrockmaster.application.companion import Companion, Notification
from edrockmaster.application.settings import DEFAULT_SETTINGS
from edrockmaster.domain.bounty.hunting import (
    CommunityGoalsChanged,
    HuntEnded,
    HuntEndReason,
    HuntStats,
    VouchersUpdated,
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
        for line in (FIXTURES / fixture).read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            produced = self.companion.handle_journal_entry(record["entry"], record["is_beta"])
            self.presenter.apply(produced)
            self.notifications += produced


@pytest.fixture(scope="module")
def conflict_zone() -> Replay:
    """40 minutes in a war conflict zone at Redonesses during a community goal (4.4.1.1),
    then a visit to the community goal's tab at the station."""
    return Replay("redonesses-conflict-zone-2026-10-03.jsonl")


def test_conflict_zone_kills_and_combat_bonds(conflict_zone: Replay) -> None:
    stats = conflict_zone.companion.hunting.current_stats
    assert stats is not None
    assert (stats.kills, stats.shared_kills) == (6, 0)
    assert (stats.bounty_credits, stats.bond_credits) == (0, 224_467)
    # Time on site: from the drop at 11:38:45 to the departure, and back to the station
    assert stats.active_duration == timedelta(minutes=26, seconds=8)


def test_conflict_zone_redemption_includes_bonds_earned_before_edmc(
    conflict_zone: Replay,
) -> None:
    # 855,491 CR redeemed, more than the 224,467 CR seen: the rest predates EDMC's start
    assert conflict_zone.companion.hunting.vouchers.total == 0


def test_conflict_zone_community_goal(conflict_zone: Replay) -> None:
    [goal] = conflict_zone.companion.hunting.community_goals
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


def test_conflict_zone_panel_shows_the_hunt(conflict_zone: Replay) -> None:
    assert conflict_zone.presenter.current is Activity.BOUNTY_HUNTING
    model = conflict_zone.presenter.render()
    assert model.status == "Conflict zone"
    lines = [(line.label, line.value) for line in model.lines]
    assert ("Combat bonds", "224,467 CR") in lines
    assert ("Éliminez les pilotes criminels…", "2,408,404, top 50 %") in lines


def test_conflict_zone_panel_does_not_show_empty_bounties(conflict_zone: Replay) -> None:
    labels = [line.label for line in conflict_zone.presenter.render().lines]
    assert "Bounties" not in labels


@pytest.fixture(scope="module")
def zone_then_bounties() -> Replay:
    """The same day: 40 more minutes in that conflict zone (EDMC started while docked), two
    game restarts, then 17 bounties at a resource site, a crime and a redemption."""
    return Replay("redonesses-conflict-zone-then-bounties-2026-10-03.jsonl")


def ended_hunts(replay: Replay) -> list[HuntStats]:
    return [n.stats for n in replay.notifications if isinstance(n, HuntEnded)]


def test_each_game_exit_ends_its_hunt(zone_then_bounties: Replay) -> None:
    reasons = [n.reason for n in zone_then_bounties.notifications if isinstance(n, HuntEnded)]
    assert reasons == [HuntEndReason.GAME_CLOSED, HuntEndReason.GAME_CLOSED]
    assert zone_then_bounties.companion.hunting.current_stats is None


def test_conflict_zone_hunt_figures(zone_then_bounties: Replay) -> None:
    zone = ended_hunts(zone_then_bounties)[0]
    assert (zone.kills, zone.bounty_credits, zone.bond_credits) == (22, 0, 817_256)
    assert zone.active_duration == timedelta(minutes=30, seconds=16)


def test_bounty_hunt_figures(zone_then_bounties: Replay) -> None:
    hunt = ended_hunts(zone_then_bounties)[1]
    assert (hunt.kills, hunt.bounty_credits, hunt.bond_credits) == (17, 6_110_097, 0)
    # 19 min 48 s of search between the first and the second bounty count: time on site
    # (gaps between rewards gave 10 min 09 s and 36 M CR/h)
    assert hunt.active_duration == timedelta(minutes=36, seconds=35)
    assert round(hunt.credits_per_hour) == 10_021_116


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


def test_panel_after_the_bounty_hunt(zone_then_bounties: Replay) -> None:
    model = zone_then_bounties.presenter.render()
    assert model.status == "Hunt ended: game closed"
    lines = [(line.label, line.value) for line in model.lines]
    assert ("Bounties", "6,110,097 CR") in lines
    assert ("Rate", "10,021,116 CR/h") in lines
    assert zone_then_bounties.companion.mining.current_stats is None
