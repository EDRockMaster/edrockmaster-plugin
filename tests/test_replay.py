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
    """40 minutes in a war conflict zone at Redonesses during a community goal (4.4.1.1)."""
    return Replay("conflict-zone-2026-10-03.jsonl")


def test_conflict_zone_kills_and_combat_bonds(conflict_zone: Replay) -> None:
    stats = conflict_zone.companion.hunting.current_stats
    assert stats is not None
    assert (stats.kills, stats.shared_kills) == (6, 0)
    assert (stats.bounty_credits, stats.bond_credits) == (0, 224_467)
    assert stats.active_duration == timedelta(minutes=17, seconds=29)


def test_conflict_zone_redemption_includes_bonds_earned_before_edmc(
    conflict_zone: Replay,
) -> None:
    # 855,491 CR redeemed, more than the 224,467 CR seen: the rest predates EDMC's start
    assert conflict_zone.companion.hunting.vouchers.total == 0


def test_conflict_zone_community_goal(conflict_zone: Replay) -> None:
    [goal] = conflict_zone.companion.hunting.community_goals
    assert (goal.cgid, goal.contribution, goal.percentile_band) == (860, 1_552_913, 75)
    assert (goal.tier_reached, goal.top_tier, goal.complete) == (None, "Tier 5", False)
    assert goal.system == "Redonesses"


def test_conflict_zone_is_not_mining(conflict_zone: Replay) -> None:
    assert conflict_zone.companion.mining.current_stats is None
    assert conflict_zone.notifier.notified == []


def test_conflict_zone_panel_shows_the_hunt(conflict_zone: Replay) -> None:
    assert conflict_zone.presenter.current is Activity.BOUNTY_HUNTING
    model = conflict_zone.presenter.render()
    assert model.status == "Bounty hunting"
    assert ("Combat bonds", "224,467 CR") in [(line.label, line.value) for line in model.lines]


def test_conflict_zone_panel_does_not_show_empty_bounties(conflict_zone: Replay) -> None:
    labels = [line.label for line in conflict_zone.presenter.render().lines]
    assert "Bounties" not in labels
