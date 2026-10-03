"""Logic of the preferences tab, without tkinter.

The tab shows ``PreferencesValues`` (texts and flags, as the widgets hold them)
and gives them back when the dialog closes. Invalid entries never reach the
settings: each keeps its previous value and is reported to the player.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from edrockmaster.application.settings import PluginSettings
from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.mining.journal import ContentLevel
from edrockmaster.domain.mining.prospecting import AlertSettings
from edrockmaster.ui.commodity_names import MINEABLE, commodity_name
from edrockmaster.ui.panel_model import NumberFormat

type NumberParser = Callable[[str], float | None]
"""Parses a number typed by the player (locale-aware in EDMC), ``None`` if invalid."""


@dataclass(slots=True)
class PreferencesValues:
    thresholds: dict[str, str]
    """Commodity key → percent as typed; empty means no alert for that commodity."""
    minimum_content: ContentLevel
    minimum_remaining: str
    alert_on_cores: bool
    sound_enabled: bool
    record_journal: bool


class _InvalidEntryError(ValueError):
    pass


def format_percent(value: float, format_number: NumberFormat) -> str:
    for decimals in range(3):
        if round(value, decimals) == value:
            return format_number(value, decimals)
    return format_number(value, 2)


def threshold_rows(
    settings: PluginSettings, translate: Callable[[str], str]
) -> list[tuple[str, str]]:
    """Commodity key and display name of each threshold field, in display order."""
    known = {key for key, _ in MINEABLE}
    extra = sorted(
        (commodity.key, commodity_name(commodity, translate))
        for commodity in settings.alerts.thresholds
        if commodity.key not in known
    )
    rows = [(key, commodity_name(Commodity(key), translate)) for key, _ in MINEABLE]
    return sorted(rows, key=lambda row: row[1].casefold()) + extra


def values_from_settings(
    settings: PluginSettings, format_number: NumberFormat
) -> PreferencesValues:
    alerts = settings.alerts
    thresholds = {key: "" for key, _ in MINEABLE}
    thresholds.update(
        {
            commodity.key: format_percent(value, format_number)
            for commodity, value in alerts.thresholds.items()
        }
    )
    remaining = alerts.minimum_remaining
    return PreferencesValues(
        thresholds=thresholds,
        minimum_content=alerts.minimum_content,
        minimum_remaining="" if remaining is None else format_percent(remaining, format_number),
        alert_on_cores=alerts.alert_on_cores,
        sound_enabled=settings.sound_enabled,
        record_journal=settings.record_journal,
    )


def settings_from_values(
    values: PreferencesValues,
    previous: PluginSettings,
    parse_number: NumberParser,
    translate: Callable[[str], str],
) -> tuple[PluginSettings, tuple[str, ...]]:
    """Return the new settings and the names of the fields whose entry was invalid."""
    invalid: list[str] = []
    thresholds: dict[Commodity, float] = {}
    for key, text in values.thresholds.items():
        commodity = Commodity(key)
        try:
            percent = _percent(text, parse_number)
        except _InvalidEntryError:
            invalid.append(commodity_name(commodity, translate))
            percent = previous.alerts.thresholds.get(commodity)
        if percent is not None:
            thresholds[commodity] = percent
    try:
        remaining = _percent(values.minimum_remaining, parse_number)
    except _InvalidEntryError:
        invalid.append(translate("Minimum remaining"))
        remaining = previous.alerts.minimum_remaining
    settings = PluginSettings(
        alerts=AlertSettings(
            thresholds=thresholds,
            minimum_content=values.minimum_content,
            minimum_remaining=remaining,
            alert_on_cores=values.alert_on_cores,
        ),
        sound_enabled=values.sound_enabled,
        record_journal=values.record_journal,
    )
    return settings, tuple(invalid)


def _percent(text: str, parse_number: NumberParser) -> float | None:
    if not text.strip():
        return None
    value = parse_number(text.strip())
    if value is None or not 0.0 <= value <= 100.0:
        raise _InvalidEntryError(text)
    return float(value)
