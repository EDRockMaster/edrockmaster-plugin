from dataclasses import replace
from datetime import timedelta

import pytest

from edrockmaster.application.activity import Activity
from edrockmaster.application.companion import Companion
from edrockmaster.application.settings import DEFAULT_SETTINGS, PluginSettings
from edrockmaster.domain.combat.session import CombatEnded, CombatStarted, VouchersUpdated
from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.mining.journal import ContentLevel
from edrockmaster.domain.mining.prospecting import AlertSettings, ProspectorAlertRaised
from edrockmaster.domain.mining.session import SessionEnded, SessionStarted
from edrockmaster.domain.trade.session import TradeEnded, TradeStarted
from tests.fakes import FakeNotifier, FakeRecorder, FakeSettingsStore, FixedClock
from tests.journal_entries import (
    T0,
    bounty_entry,
    market_buy_entry,
    prospected_entry,
    refined_entry,
    timestamp,
)

PAINITE = Commodity.from_symbol("painite")


class Harness:
    def __init__(self, settings: PluginSettings = DEFAULT_SETTINGS) -> None:
        self.store = FakeSettingsStore(settings)
        self.notifier = FakeNotifier()
        self.recorder = FakeRecorder()
        self.clock = FixedClock(T0 + timedelta(hours=1))
        self.companion = Companion(
            settings_store=self.store,
            notifier=self.notifier,
            recorder=self.recorder,
            clock=self.clock,
        )

    def entry(self, entry: Entry, is_beta: bool = False) -> list[object]:
        return list(self.companion.handle_journal_entry(entry, is_beta))


@pytest.fixture
def harness() -> Harness:
    return Harness()


# --- dispatch to the activities -----------------------------------------------------------


def test_each_activity_receives_the_entries(harness: Harness) -> None:
    assert isinstance(harness.entry(prospected_entry(0))[0], SessionStarted)
    assert isinstance(harness.entry(bounty_entry(1))[0], CombatStarted)
    assert isinstance(harness.entry(market_buy_entry(2))[0], TradeStarted)
    assert harness.companion.mining.current_stats is not None
    assert harness.companion.combat.current_stats is not None
    assert harness.companion.trade.current_stats is not None


def test_irrelevant_entries_produce_nothing(harness: Harness) -> None:
    entry: Entry = {"timestamp": timestamp(0), "event": "Music"}
    assert harness.entry(entry) == []


def test_reset_acts_on_the_chosen_activity_only(harness: Harness) -> None:
    harness.entry(refined_entry(0))
    harness.entry(bounty_entry(1))
    harness.entry(market_buy_entry(2))
    [ended] = harness.companion.reset(Activity.COMBAT)
    assert isinstance(ended, CombatEnded)
    assert harness.companion.mining.current_stats is not None
    [ended] = harness.companion.reset(Activity.TRADE)
    assert isinstance(ended, TradeEnded)
    assert harness.companion.mining.current_stats is not None
    [ended] = harness.companion.reset(Activity.MINING)
    assert isinstance(ended, SessionEnded)
    assert ended.at == harness.clock.current


def test_alerts_still_sound(harness: Harness) -> None:
    harness.entry(prospected_entry(0, painite=40.0))
    assert len(harness.notifier.notified) == 1


def test_vouchers_are_notified_with_the_kill(harness: Harness) -> None:
    assert any(isinstance(n, VouchersUpdated) for n in harness.entry(bounty_entry(0)))


# --- journal recorder ---------------------------------------------------------------------


def test_recorder_is_off_by_default(harness: Harness) -> None:
    harness.entry(refined_entry(0))
    assert harness.recorder.recorded == []


def test_recorder_copies_every_entry_once_when_enabled() -> None:
    harness = Harness(replace(DEFAULT_SETTINGS, record_journal=True))
    music: Entry = {"timestamp": timestamp(0), "event": "Music", "MusicTrack": "Exploration"}
    refined = refined_entry(1)
    harness.entry(music)
    harness.entry(refined, is_beta=True)
    assert harness.recorder.recorded == [(music, False), (refined, True)]


# --- settings -----------------------------------------------------------------------------


def test_settings_are_loaded_from_the_store() -> None:
    custom = replace(DEFAULT_SETTINGS, sound_enabled=False)
    assert Harness(custom).companion.settings == custom


def test_changed_settings_are_saved_and_applied(harness: Harness) -> None:
    strict = replace(
        DEFAULT_SETTINGS,
        alerts=AlertSettings(
            thresholds={PAINITE: 50.0},
            minimum_content=ContentLevel.LOW,
            minimum_remaining=None,
            alert_on_cores=True,
        ),
        record_journal=True,
    )
    harness.companion.change_settings(strict)
    assert harness.store.stored == strict
    assert harness.store.saves == 1
    assert harness.companion.settings == strict
    notifications = harness.entry(prospected_entry(1, painite=30.0))
    assert not any(isinstance(n, ProspectorAlertRaised) for n in notifications)
    assert len(harness.recorder.recorded) == 1


def test_unchanged_settings_are_not_saved_again(harness: Harness) -> None:
    harness.companion.change_settings(DEFAULT_SETTINGS)
    assert harness.store.saves == 0
