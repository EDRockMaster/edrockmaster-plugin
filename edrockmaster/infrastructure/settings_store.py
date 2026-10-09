"""Settings stored in a key-value store (``settings_file.py``), as the EDMC plugin stored them.

Every key is prefixed with ``edrockmaster.``. Values are read one by one: an
invalid value falls back to its own default and is logged, the others are kept.
Numbers are stored as text.

The activities shown are stored with the activities the tab offered: one that
a later version adds is shown until the player hides it.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Protocol

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

SETTINGS_VERSION = "1"

KEY_VERSION = "edrockmaster.settings_version"
KEY_THRESHOLDS = "edrockmaster.alert.thresholds"
KEY_MINIMUM_CONTENT = "edrockmaster.alert.minimum_content"
KEY_MINIMUM_REMAINING = "edrockmaster.alert.minimum_remaining"
KEY_CORES = "edrockmaster.alert.cores"
KEY_SOUND = "edrockmaster.sound"
KEY_RECORD_JOURNAL = "edrockmaster.record_journal"
KEY_DISPLAY_ACTIVITIES = "edrockmaster.display.activities"
KEY_DISPLAY_MODE = "edrockmaster.display.mode"
KEY_DISPLAY_OFFERED = "edrockmaster.display.offered"

OFFERED_BEFORE_TRADE: tuple[Activity, ...] = (Activity.MINING, Activity.COMBAT)
"""What the tab offered when the settings were saved without ``KEY_DISPLAY_OFFERED`` (0.3.0)."""

_MINIMUM_CONTENTS = {
    level.value: level for level in ContentLevel if level is not ContentLevel.UNKNOWN
}


class ConfigStore(Protocol):
    """What the settings need of a key-value store."""

    def get_str(self, key: str, /, *, default: str | None = None) -> str | None: ...

    def get_bool(self, key: str, /, *, default: bool | None = None) -> bool: ...

    def set(self, key: str, value: str | bool, /) -> None: ...


class _InvalidValueError(ValueError):
    pass


class KeyValueSettingsStore:
    def __init__(self, config: ConfigStore, logger: logging.Logger) -> None:
        self._config = config
        self._logger = logger

    def load(self) -> PluginSettings:
        defaults = DEFAULT_SETTINGS
        alerts = AlertSettings(
            thresholds=self._read(KEY_THRESHOLDS, _parse_thresholds, defaults.alerts.thresholds),
            minimum_content=self._read(
                KEY_MINIMUM_CONTENT, _parse_content, defaults.alerts.minimum_content
            ),
            minimum_remaining=self._read(
                KEY_MINIMUM_REMAINING, _parse_remaining, defaults.alerts.minimum_remaining
            ),
            alert_on_cores=self._read_bool(KEY_CORES, defaults.alerts.alert_on_cores),
        )
        return PluginSettings(
            alerts=alerts,
            sound_enabled=self._read_bool(KEY_SOUND, defaults.sound_enabled),
            record_journal=self._read_bool(KEY_RECORD_JOURNAL, defaults.record_journal),
            display=DisplaySettings(
                activities=self._read_activities(defaults.display.activities),
                mode=self._read(KEY_DISPLAY_MODE, _parse_mode, defaults.display.mode),
            ),
        )

    def _read_activities(self, default: tuple[Activity, ...]) -> tuple[Activity, ...]:
        shown = self._read(KEY_DISPLAY_ACTIVITIES, _parse_activities, None)
        if shown is None:
            return default
        offered = self._read(KEY_DISPLAY_OFFERED, _parse_activities, OFFERED_BEFORE_TRADE)
        return (*shown, *(activity for activity in Activity if activity not in offered))

    def save(self, settings: PluginSettings) -> None:
        alerts = settings.alerts
        thresholds = {commodity.key: value for commodity, value in alerts.thresholds.items()}
        remaining = alerts.minimum_remaining
        self._config.set(KEY_VERSION, SETTINGS_VERSION)
        self._config.set(KEY_THRESHOLDS, json.dumps(thresholds, sort_keys=True))
        self._config.set(KEY_MINIMUM_CONTENT, alerts.minimum_content.value)
        self._config.set(KEY_MINIMUM_REMAINING, "" if remaining is None else repr(remaining))
        self._config.set(KEY_CORES, alerts.alert_on_cores)
        self._config.set(KEY_SOUND, settings.sound_enabled)
        self._config.set(KEY_RECORD_JOURNAL, settings.record_journal)
        activities = [activity.value for activity in settings.display.activities]
        self._config.set(KEY_DISPLAY_ACTIVITIES, json.dumps(activities))
        self._config.set(KEY_DISPLAY_OFFERED, json.dumps([activity.value for activity in Activity]))
        self._config.set(KEY_DISPLAY_MODE, settings.display.mode.value)

    def _read[T](self, key: str, parse: Callable[[str], T], default: T) -> T:
        try:
            raw = self._config.get_str(key, default=None)
            return default if raw is None else parse(raw)
        except ValueError as error:
            self._logger.warning("Invalid setting %s (%s), using the default", key, error)
            return default

    def _read_bool(self, key: str, default: bool) -> bool:
        try:
            return self._config.get_bool(key, default=default)
        except ValueError as error:
            self._logger.warning("Invalid setting %s (%s), using the default", key, error)
            return default


def _percent(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _InvalidValueError(f"not a number: {value!r}")
    if not 0.0 <= value <= 100.0:
        raise _InvalidValueError(f"out of range: {value!r}")
    return float(value)


def _parse_thresholds(raw: str) -> dict[Commodity, float]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise _InvalidValueError("thresholds are not valid JSON") from error
    if not isinstance(data, dict):
        raise _InvalidValueError("thresholds must be a JSON object")
    try:
        return {Commodity.from_symbol(key): _percent(value) for key, value in data.items()}
    except ValueError as error:
        raise _InvalidValueError(f"thresholds: {error}") from error


def _parse_content(raw: str) -> ContentLevel:
    try:
        return _MINIMUM_CONTENTS[raw]
    except KeyError as error:
        raise _InvalidValueError(f"unknown content level: {raw!r}") from error


def _parse_remaining(raw: str) -> float | None:
    if not raw:
        return None
    try:
        return _percent(float(raw))
    except ValueError as error:
        raise _InvalidValueError(f"minimum remaining: {error}") from error


def _parse_activities(raw: str) -> tuple[Activity, ...]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise _InvalidValueError("activities are not valid JSON") from error
    if not isinstance(data, list) or not data:
        raise _InvalidValueError("activities must be a non-empty JSON list")
    try:
        return tuple(Activity(value) for value in data)
    except ValueError as error:
        raise _InvalidValueError(f"activities: {error}") from error


def _parse_mode(raw: str) -> DisplayMode:
    try:
        return DisplayMode(raw)
    except ValueError as error:
        raise _InvalidValueError(f"unknown display mode: {raw!r}") from error
