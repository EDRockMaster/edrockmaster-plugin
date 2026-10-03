from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.application.mining_service import MiningService
from edrockmaster.application.settings import DEFAULT_SETTINGS, PluginSettings
from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.journal import ContentLevel, Entry
from edrockmaster.domain.prospecting import (
    AlertSettings,
    CommodityAlert,
    CoreAlert,
    ProspectorAlertRaised,
)
from edrockmaster.domain.session import (
    EndReason,
    SessionEnded,
    SessionStarted,
    SessionUpdated,
)

T0 = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
PAINITE = Commodity.from_symbol("painite")
PLATINUM = Commodity.from_symbol("platinum")


# --- test doubles -------------------------------------------------------------------------


class FakeSettingsStore:
    def __init__(self, settings: PluginSettings = DEFAULT_SETTINGS) -> None:
        self.stored = settings
        self.saves = 0

    def load(self) -> PluginSettings:
        return self.stored

    def save(self, settings: PluginSettings) -> None:
        self.stored = settings
        self.saves += 1


class FakeNotifier:
    def __init__(self) -> None:
        self.notified: list[ProspectorAlertRaised] = []

    def notify(self, alert: ProspectorAlertRaised) -> None:
        self.notified.append(alert)


class FakeRecorder:
    def __init__(self) -> None:
        self.recorded: list[tuple[Entry, bool]] = []

    def record(self, entry: Entry, is_beta: bool) -> None:
        self.recorded.append((entry, is_beta))


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


# --- journal entries ----------------------------------------------------------------------


def timestamp(minutes: float) -> str:
    return (T0 + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def ring_entry(minutes: float = 0) -> Entry:
    return {
        "timestamp": timestamp(minutes),
        "event": "SupercruiseExit",
        "StarSystem": "Col 285 Sector AB-C d1",
        "SystemAddress": 42,
        "Body": "Col 285 Sector AB-C d1 2 A Ring",
        "BodyType": "PlanetaryRing",
    }


def prospected_entry(
    minutes: float,
    painite: float = 30.0,
    content: str = "$AsteroidMaterialContent_High;",
    motherlode: str | None = None,
) -> Entry:
    entry: dict[str, object] = {
        "timestamp": timestamp(minutes),
        "event": "ProspectedAsteroid",
        "Materials": [
            {"Name": "Painite", "Proportion": painite},
            {"Name": "Bromellite", "Proportion": 100.0 - painite},
        ],
        "Content": content,
        "Remaining": 100.0,
    }
    if motherlode is not None:
        entry["MotherlodeMaterial"] = motherlode
    return entry


def refined_entry(minutes: float, commodity: str = "$painite_name;") -> Entry:
    return {
        "timestamp": timestamp(minutes),
        "event": "MiningRefined",
        "Type": commodity,
        "Type_Localised": "Painite",
    }


def supercruise_entry(minutes: float) -> Entry:
    return {"timestamp": timestamp(minutes), "event": "SupercruiseEntry", "StarSystem": "Col 285"}


# --- fixture ------------------------------------------------------------------------------


class Harness:
    def __init__(self, settings: PluginSettings = DEFAULT_SETTINGS) -> None:
        self.store = FakeSettingsStore(settings)
        self.notifier = FakeNotifier()
        self.recorder = FakeRecorder()
        self.clock = FixedClock(T0 + timedelta(hours=1))
        self.service = MiningService(
            settings_store=self.store,
            notifier=self.notifier,
            recorder=self.recorder,
            clock=self.clock,
        )


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


# --- journal recorder ---------------------------------------------------------------------


def test_recorder_is_off_by_default(harness: Harness) -> None:
    harness.service.handle_journal_entry(refined_entry(0), is_beta=False)
    assert harness.recorder.recorded == []


def test_recorder_copies_every_entry_when_enabled() -> None:
    harness = Harness(replace(DEFAULT_SETTINGS, record_journal=True))
    music: Entry = {"timestamp": timestamp(0), "event": "Music", "MusicTrack": "Exploration"}
    refined = refined_entry(1)
    harness.service.handle_journal_entry(music, is_beta=False)
    harness.service.handle_journal_entry(refined, is_beta=True)
    assert harness.recorder.recorded == [(music, False), (refined, True)]


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


def test_settings_are_loaded_from_the_store() -> None:
    custom = replace(DEFAULT_SETTINGS, sound_enabled=False)
    assert Harness(custom).service.settings == custom


def test_changed_settings_are_saved_and_applied(harness: Harness) -> None:
    strict = replace(
        DEFAULT_SETTINGS,
        alerts=AlertSettings(
            thresholds={PAINITE: 50.0},
            minimum_content=ContentLevel.LOW,
            minimum_remaining=None,
            alert_on_cores=True,
        ),
    )
    harness.service.change_settings(strict)
    assert harness.store.stored == strict
    assert harness.store.saves == 1
    assert harness.service.settings == strict
    notifications = harness.service.handle_journal_entry(
        prospected_entry(1, painite=30.0), is_beta=False
    )
    assert alerts_in(notifications) == []


def test_unchanged_settings_are_not_saved_again(harness: Harness) -> None:
    harness.service.change_settings(DEFAULT_SETTINGS)
    assert harness.store.saves == 0


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
