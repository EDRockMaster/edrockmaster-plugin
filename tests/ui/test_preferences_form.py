from dataclasses import replace

import pytest

from edrockmaster.application.activity import Activity
from edrockmaster.application.settings import (
    DEFAULT_SETTINGS,
    DisplayMode,
    DisplaySettings,
    PluginSettings,
)
from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.mining.journal import ContentLevel
from edrockmaster.domain.mining.prospecting import AlertSettings
from edrockmaster.ui.commodity_names import MINEABLE
from edrockmaster.ui.preferences_form import (
    PreferencesValues,
    format_percent,
    settings_from_values,
    threshold_rows,
    values_from_settings,
)

PAINITE = Commodity.from_symbol("painite")
PLATINUM = Commodity.from_symbol("platinum")
WEIRD = Commodity.from_symbol("weirdrock")


def parse(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def fmt(number: float, decimals: int) -> str:
    return f"{number:.{decimals}f}"


def identity(text: str) -> str:
    return text


def custom(**thresholds: float) -> PluginSettings:
    return replace(
        DEFAULT_SETTINGS,
        alerts=AlertSettings(
            thresholds={Commodity.from_symbol(key): value for key, value in thresholds.items()},
            minimum_content=ContentLevel.LOW,
            minimum_remaining=None,
            alert_on_cores=True,
        ),
    )


def to_settings(
    values: PreferencesValues, previous: PluginSettings = DEFAULT_SETTINGS
) -> tuple[PluginSettings, tuple[str, ...]]:
    return settings_from_values(values, previous, parse, identity)


@pytest.mark.parametrize(
    ("value", "text"), [(25.0, "25"), (32.5, "32.5"), (12.25, "12.25"), (0.0, "0"), (1 / 3, "0.33")]
)
def test_percentages_are_shown_without_useless_decimals(value: float, text: str) -> None:
    assert format_percent(value, fmt) == text


def test_rows_list_the_catalogue_then_unknown_commodities_of_the_settings() -> None:
    rows = threshold_rows(custom(weirdrock=10.0), identity)
    assert [key for key, _ in rows[: len(MINEABLE)]] == [key for key, _ in MINEABLE]
    assert rows[-1] == ("weirdrock", "weirdrock")


def test_values_show_the_settings() -> None:
    values = values_from_settings(DEFAULT_SETTINGS, fmt)
    assert values.thresholds["painite"] == "25"
    assert values.thresholds["bromellite"] == ""
    assert values.minimum_content is ContentLevel.LOW
    assert values.minimum_remaining == ""
    assert values.alert_on_cores
    assert values.sound_enabled
    assert not values.record_journal


def test_unchanged_values_give_back_the_same_settings() -> None:
    settings, invalid = to_settings(values_from_settings(DEFAULT_SETTINGS, fmt))
    assert settings == DEFAULT_SETTINGS
    assert invalid == ()


def test_edited_values_become_the_new_settings() -> None:
    values = values_from_settings(DEFAULT_SETTINGS, fmt)
    values.thresholds["painite"] = "40"
    values.thresholds["platinum"] = "  "
    values.thresholds["bromellite"] = "55.5"
    values.minimum_content = ContentLevel.HIGH
    values.minimum_remaining = "50"
    values.alert_on_cores = False
    values.sound_enabled = False
    values.record_journal = True
    settings, invalid = to_settings(values)
    assert invalid == ()
    assert settings.alerts.thresholds[PAINITE] == 40.0
    assert PLATINUM not in settings.alerts.thresholds
    assert settings.alerts.thresholds[Commodity.from_symbol("bromellite")] == 55.5
    assert settings.alerts.minimum_content is ContentLevel.HIGH
    assert settings.alerts.minimum_remaining == 50.0
    assert not settings.alerts.alert_on_cores
    assert not settings.sound_enabled
    assert settings.record_journal


@pytest.mark.parametrize("text", ["lots", "150", "-1"])
def test_an_invalid_threshold_keeps_its_previous_value_and_is_reported(text: str) -> None:
    values = values_from_settings(DEFAULT_SETTINGS, fmt)
    values.thresholds["painite"] = text
    values.thresholds["osmium"] = "30"
    settings, invalid = to_settings(values)
    assert settings.alerts.thresholds[PAINITE] == 25.0
    assert settings.alerts.thresholds[Commodity.from_symbol("osmium")] == 30.0
    assert invalid == ("Painite",)


def test_an_invalid_new_threshold_is_left_out() -> None:
    values = values_from_settings(DEFAULT_SETTINGS, fmt)
    values.thresholds["bromellite"] = "lots"
    settings, invalid = to_settings(values)
    assert Commodity.from_symbol("bromellite") not in settings.alerts.thresholds
    assert invalid == ("Bromellite",)


def test_an_invalid_minimum_remaining_keeps_its_previous_value() -> None:
    previous = replace(
        DEFAULT_SETTINGS, alerts=replace(DEFAULT_SETTINGS.alerts, minimum_remaining=40.0)
    )
    values = values_from_settings(previous, fmt)
    values.minimum_remaining = "a lot"
    settings, invalid = to_settings(values, previous)
    assert settings.alerts.minimum_remaining == 40.0
    assert invalid == ("Minimum remaining",)


def test_unknown_commodities_of_the_settings_are_kept() -> None:
    previous = custom(weirdrock=10.0)
    settings, _ = to_settings(values_from_settings(previous, fmt), previous)
    assert settings.alerts.thresholds[WEIRD] == 10.0


def test_values_show_the_display_settings() -> None:
    values = values_from_settings(DEFAULT_SETTINGS, fmt)
    assert values.activities == {
        Activity.MINING: True,
        Activity.COMBAT: True,
        Activity.TRADE: True,
        Activity.ENGINEERING: True,
    }
    assert values.display_mode is DisplayMode.LAST_ACTIVE


def test_edited_display_becomes_the_new_settings() -> None:
    values = values_from_settings(DEFAULT_SETTINGS, fmt)
    values.activities[Activity.MINING] = False
    values.display_mode = DisplayMode.STACKED
    settings, invalid = to_settings(values)
    assert settings.display == DisplaySettings(
        (Activity.COMBAT, Activity.TRADE, Activity.ENGINEERING), DisplayMode.STACKED
    )
    assert invalid == ()


def test_hiding_every_activity_keeps_the_previous_ones_and_is_reported() -> None:
    previous = replace(DEFAULT_SETTINGS, display=DisplaySettings((Activity.COMBAT,)))
    values = values_from_settings(previous, fmt)
    values.activities[Activity.COMBAT] = False
    values.display_mode = DisplayMode.STACKED
    settings, invalid = to_settings(values, previous)
    assert settings.display == DisplaySettings((Activity.COMBAT,), DisplayMode.STACKED)
    assert invalid == ("Activities shown",)
