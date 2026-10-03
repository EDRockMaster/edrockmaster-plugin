from collections.abc import Sequence
from dataclasses import replace
from datetime import timedelta

import pytest

from edrockmaster.application.mining_service import MiningService
from edrockmaster.application.settings import DEFAULT_SETTINGS, PluginSettings
from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.mining.journal import ContentLevel
from edrockmaster.domain.mining.prospecting import (
    AlertSettings,
    CommodityAlert,
    CoreAlert,
    ProspectorAlertRaised,
)
from edrockmaster.domain.mining.session import (
    EndReason,
    SessionEnded,
    SessionStarted,
    SessionUpdated,
)
from tests.fakes import FakeNotifier, FixedClock
from tests.journal_entries import (
    T0,
    prospected_entry,
    refined_entry,
    ring_entry,
    supercruise_entry,
    timestamp,
)

PAINITE = Commodity.from_symbol("painite")
PLATINUM = Commodity.from_symbol("platinum")


# --- fixture ------------------------------------------------------------------------------


class Harness:
    def __init__(self, settings: PluginSettings = DEFAULT_SETTINGS) -> None:
        self.notifier = FakeNotifier()
        self.clock = FixedClock(T0 + timedelta(hours=1))
        self.service = MiningService(settings=settings, notifier=self.notifier, clock=self.clock)


@pytest.fixture
def harness() -> Harness:
    return Harness()


def alerts_in(notifications: Sequence[object]) -> list[ProspectorAlertRaised]:
    return [n for n in notifications if isinstance(n, ProspectorAlertRaised)]


# --- journal entries ----------------------------------------------------------------------


def test_irrelevant_entries_produce_nothing(harness: Harness) -> None:
    entry: Entry = {"timestamp": timestamp(0), "event": "Music", "MusicTrack": "Exploration"}
    assert harness.service.handle_journal_entry(entry, is_beta=False) == []
    assert harness.notifier.notified == []


def test_malformed_entries_are_ignored(harness: Harness) -> None:
    entry: Entry = {"event": "MiningRefined"}
    assert harness.service.handle_journal_entry(entry, is_beta=False) == []


def test_first_prospecting_starts_a_session_in_the_current_ring(harness: Harness) -> None:
    harness.service.handle_journal_entry(ring_entry(), is_beta=False)
    notifications = harness.service.handle_journal_entry(prospected_entry(1), is_beta=False)
    started = notifications[0]
    assert isinstance(started, SessionStarted)
    assert started.ring == "Col 285 Sector AB-C d1 2 A Ring"


def test_valuable_asteroid_raises_an_audible_alert(harness: Harness) -> None:
    notifications = harness.service.handle_journal_entry(
        prospected_entry(1, painite=30.0), is_beta=False
    )
    [raised] = alerts_in(notifications)
    assert raised.alerts == (CommodityAlert(PAINITE, 30.0, 25.0),)
    assert harness.notifier.notified == [raised]


def test_poor_asteroid_raises_no_alert(harness: Harness) -> None:
    notifications = harness.service.handle_journal_entry(
        prospected_entry(1, painite=10.0), is_beta=False
    )
    assert alerts_in(notifications) == []
    assert harness.notifier.notified == []


def test_core_raises_an_alert_whatever_the_thresholds(harness: Harness) -> None:
    notifications = harness.service.handle_journal_entry(
        prospected_entry(1, painite=0.0, motherlode="Painite"), is_beta=False
    )
    [raised] = alerts_in(notifications)
    assert raised.alerts == (CoreAlert(PAINITE),)


def test_alert_is_silent_when_sound_is_disabled() -> None:
    harness = Harness(replace(DEFAULT_SETTINGS, sound_enabled=False))
    notifications = harness.service.handle_journal_entry(prospected_entry(1), is_beta=False)
    assert len(alerts_in(notifications)) == 1
    assert harness.notifier.notified == []


def test_refining_updates_the_session(harness: Harness) -> None:
    harness.service.handle_journal_entry(prospected_entry(0), is_beta=False)
    notifications = harness.service.handle_journal_entry(refined_entry(1), is_beta=False)
    [updated] = notifications
    assert isinstance(updated, SessionUpdated)
    assert updated.stats.tons_by_commodity == {PAINITE: 1}


def test_current_stats_follow_the_session(harness: Harness) -> None:
    assert harness.service.current_stats is None
    harness.service.handle_journal_entry(refined_entry(0), is_beta=False)
    stats = harness.service.current_stats
    assert stats is not None
    assert stats.total_tons == 1


def test_beta_flag_reaches_the_tracker(harness: Harness) -> None:
    assert harness.service.is_live
    harness.service.handle_journal_entry(ring_entry(), is_beta=True)
    assert not harness.service.is_live


# --- manual reset -------------------------------------------------------------------------


def test_reset_ends_the_running_session_at_the_current_time(harness: Harness) -> None:
    harness.service.handle_journal_entry(refined_entry(0), is_beta=False)
    [ended] = harness.service.reset_session()
    assert isinstance(ended, SessionEnded)
    assert ended.reason is EndReason.MANUAL
    assert ended.at == harness.clock.current
    assert harness.service.current_stats is None


def test_reset_without_session_does_nothing(harness: Harness) -> None:
    assert harness.service.reset_session() == []


# --- settings -----------------------------------------------------------------------------


def test_new_settings_apply_to_the_next_asteroids(harness: Harness) -> None:
    strict = replace(
        DEFAULT_SETTINGS,
        alerts=AlertSettings(
            thresholds={PAINITE: 50.0},
            minimum_content=ContentLevel.LOW,
            minimum_remaining=None,
            alert_on_cores=True,
        ),
    )
    harness.service.apply_settings(strict)
    notifications = harness.service.handle_journal_entry(
        prospected_entry(1, painite=30.0), is_beta=False
    )
    assert alerts_in(notifications) == []


def test_default_settings_match_the_documented_defaults() -> None:
    assert DEFAULT_SETTINGS.sound_enabled
    assert not DEFAULT_SETTINGS.record_journal
    assert DEFAULT_SETTINGS.alerts.thresholds[PAINITE] == 25.0
    assert DEFAULT_SETTINGS.alerts.thresholds[PLATINUM] == 20.0


# --- replay -------------------------------------------------------------------------------


def test_replayed_mining_run_yields_consistent_statistics(harness: Harness) -> None:
    entries = [
        ring_entry(0),
        prospected_entry(1, painite=30.0),
        refined_entry(2),
        refined_entry(3),
        prospected_entry(4, painite=10.0),
        refined_entry(5, "$platinum_name;"),
        refined_entry(7),
        supercruise_entry(8),
    ]
    notifications = [
        notification
        for entry in entries
        for notification in harness.service.handle_journal_entry(entry, is_beta=False)
    ]
    ended = notifications[-1]
    assert isinstance(ended, SessionEnded)
    assert ended.reason is EndReason.SUPERCRUISE
    assert ended.stats.tons_by_commodity == {PAINITE: 3, PLATINUM: 1}
    assert ended.stats.active_duration == timedelta(minutes=6)
    assert ended.stats.tons_per_hour == pytest.approx(40.0)
    assert len(alerts_in(notifications)) == 1
    assert harness.service.current_stats is None
