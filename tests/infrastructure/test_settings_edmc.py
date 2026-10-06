import json
import logging
from dataclasses import replace

import pytest

from edrockmaster.application.activity import Activity
from edrockmaster.application.settings import DEFAULT_SETTINGS, DisplayMode, DisplaySettings
from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.mining.journal import ContentLevel
from edrockmaster.domain.mining.prospecting import AlertSettings
from edrockmaster.infrastructure.settings_edmc import EdmcSettingsStore
from tests.fakes import FakeConfig

PAINITE = Commodity.from_symbol("painite")
OSMIUM = Commodity.from_symbol("osmium")

logger = logging.getLogger("test.settings")


CUSTOM = replace(
    DEFAULT_SETTINGS,
    alerts=AlertSettings(
        thresholds={PAINITE: 40.0, OSMIUM: 32.5},
        minimum_content=ContentLevel.MEDIUM,
        minimum_remaining=50.0,
        alert_on_cores=False,
    ),
    sound_enabled=False,
    record_journal=True,
    display=DisplaySettings((Activity.COMBAT,), DisplayMode.STACKED),
)


def test_empty_config_yields_the_defaults() -> None:
    assert EdmcSettingsStore(FakeConfig(), logger).load() == DEFAULT_SETTINGS


def test_saved_settings_load_back_identical() -> None:
    config = FakeConfig()
    EdmcSettingsStore(config, logger).save(CUSTOM)
    assert EdmcSettingsStore(config, logger).load() == CUSTOM


def test_keys_are_prefixed_and_versioned() -> None:
    config = FakeConfig()
    EdmcSettingsStore(config, logger).save(CUSTOM)
    assert all(key.startswith("edrockmaster.") for key in config.values)
    assert config.values["edrockmaster.settings_version"] == "1"


def test_minimum_remaining_none_round_trips() -> None:
    config = FakeConfig()
    EdmcSettingsStore(config, logger).save(DEFAULT_SETTINGS)
    assert EdmcSettingsStore(config, logger).load().alerts.minimum_remaining is None


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("edrockmaster.alert.thresholds", "not json"),
        ("edrockmaster.alert.thresholds", json.dumps(["painite"])),
        ("edrockmaster.alert.thresholds", json.dumps({"painite": "high"})),
        ("edrockmaster.alert.thresholds", json.dumps({"painite": 150})),
        ("edrockmaster.alert.thresholds", json.dumps({"painite": True})),
        ("edrockmaster.alert.thresholds", json.dumps({"": 20})),
    ],
)
def test_invalid_thresholds_fall_back_to_the_defaults(
    key: str, value: str, caplog: pytest.LogCaptureFixture
) -> None:
    store = EdmcSettingsStore(FakeConfig({key: value}), logger)
    with caplog.at_level(logging.WARNING):
        settings = store.load()
    assert settings.alerts.thresholds == DEFAULT_SETTINGS.alerts.thresholds
    assert "thresholds" in caplog.text


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("edrockmaster.alert.minimum_content", "excellent"),
        ("edrockmaster.alert.minimum_remaining", "lots"),
        ("edrockmaster.alert.minimum_remaining", "120"),
        ("edrockmaster.alert.cores", "yes"),
        ("edrockmaster.sound", 1),
        ("edrockmaster.display.activities", "mining"),
        ("edrockmaster.display.activities", "[]"),
        ("edrockmaster.display.activities", '["fishing"]'),
        ("edrockmaster.display.activities", '{"mining": true}'),
        ("edrockmaster.display.mode", "sideways"),
    ],
)
def test_each_invalid_value_falls_back_to_its_own_default(key: str, value: object) -> None:
    config = FakeConfig()
    store = EdmcSettingsStore(config, logger)
    store.save(CUSTOM)
    config.values[key] = value
    settings = store.load()
    assert settings != CUSTOM
    assert settings.record_journal  # the other values are kept
    assert settings.alerts.thresholds == CUSTOM.alerts.thresholds


def test_display_is_stored_as_text() -> None:
    config = FakeConfig()
    EdmcSettingsStore(config, logger).save(CUSTOM)
    assert config.values["edrockmaster.display.activities"] == '["combat"]'
    assert config.values["edrockmaster.display.mode"] == "stacked"
    assert config.values["edrockmaster.display.offered"] == '["mining", "combat", "trade"]'


def test_an_activity_the_tab_did_not_offer_is_shown() -> None:
    # Saved by 0.3.0, before trade existed: no list of the activities offered
    config = FakeConfig()
    config.values["edrockmaster.display.activities"] = '["combat"]'
    display = EdmcSettingsStore(config, logger).load().display
    assert display.activities == (Activity.COMBAT, Activity.TRADE)


def test_an_activity_hidden_after_it_was_offered_stays_hidden() -> None:
    config = FakeConfig()
    config.values["edrockmaster.display.activities"] = '["combat"]'
    config.values["edrockmaster.display.offered"] = '["mining", "combat", "trade"]'
    display = EdmcSettingsStore(config, logger).load().display
    assert display.activities == (Activity.COMBAT,)


def test_an_invalid_list_of_offered_activities_is_the_one_of_0_3_0() -> None:
    config = FakeConfig()
    config.values["edrockmaster.display.activities"] = '["mining"]'
    config.values["edrockmaster.display.offered"] = "trade"
    display = EdmcSettingsStore(config, logger).load().display
    assert display.activities == (Activity.MINING, Activity.TRADE)
