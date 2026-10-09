"""The desktop application's settings view (ADR 0020, ADR 0021).

The player's settings are the plugin's (alerts, sound, journal recordings, the
activities shown), stored with the same keys (``settings.json``). The desktop
application adds two of its own: the **language** of its texts (the system's
by default), applied at once, and the **journal folder** when the game's is not
where it is usually found, applied at the next start (reading another folder
at once would count its sessions on top of the current ones).

``settings_view`` gives the interface what its form shows; ``settings_from_request``
turns the form back into settings, refusing what is not valid.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from edrockmaster.application.activity import Activity
from edrockmaster.application.settings import DisplaySettings, PluginSettings
from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.mining.journal import ContentLevel
from edrockmaster.domain.mining.prospecting import AlertSettings
from edrockmaster.infrastructure.settings_edmc import EdmcConfig
from edrockmaster.ui.commodity_names import MINEABLE

LANGUAGES = ("auto", "en", "fr")
KEY_LANGUAGE = "edrockmaster.desktop.language"
KEY_JOURNAL_FOLDER = "edrockmaster.desktop.journal_folder"
_CONTENTS = {level.value: level for level in ContentLevel if level is not ContentLevel.UNKNOWN}


class SettingsError(ValueError):
    """A field of the form is not valid; ``field`` names it."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field


@dataclass(frozen=True, slots=True)
class DesktopPreferences:
    language: str = "auto"
    """``auto`` (the system's), ``en`` or ``fr``."""
    journal_folder: str | None = None
    """The journal folder set by hand; ``None``: where the game usually writes it."""


class DesktopPreferencesStore:
    """The desktop application's own settings, next to the plugin's in ``settings.json``."""

    def __init__(self, config: EdmcConfig) -> None:
        self._config = config

    def load(self) -> DesktopPreferences:
        language = self._config.get_str(KEY_LANGUAGE, default="auto") or "auto"
        folder = self._config.get_str(KEY_JOURNAL_FOLDER, default="") or None
        return DesktopPreferences(language if language in LANGUAGES else "auto", folder)

    def save(self, preferences: DesktopPreferences) -> None:
        self._config.set(KEY_LANGUAGE, preferences.language)
        self._config.set(KEY_JOURNAL_FOLDER, preferences.journal_folder or "")


def settings_view(
    settings: PluginSettings,
    preferences: DesktopPreferences,
    journal_in_use: Path | None,
    translate: Callable[[str], str],
) -> dict[str, Any]:
    alerts = settings.alerts
    thresholds = {commodity.key: value for commodity, value in alerts.thresholds.items()}
    return {
        "alerts": {
            "thresholds": [
                {"commodity": key, "name": translate(name), "threshold": thresholds.get(key)}
                for key, name in MINEABLE
            ],
            "minimumContent": alerts.minimum_content.value
            if alerts.minimum_content in _CONTENTS.values()
            else ContentLevel.LOW.value,
            "minimumRemaining": alerts.minimum_remaining,
            "cores": alerts.alert_on_cores,
        },
        "sound": settings.sound_enabled,
        "recordJournal": settings.record_journal,
        "activities": [activity.value for activity in settings.display.activities],
        "language": preferences.language,
        "journalFolder": preferences.journal_folder,
        "journalFolderInUse": str(journal_in_use) if journal_in_use else None,
    }


def settings_from_request(
    request: Mapping[str, Any], current: PluginSettings
) -> tuple[PluginSettings, DesktopPreferences]:
    """The settings the form asks for; ``SettingsError`` names the first invalid field."""
    alerts = _mapping(request, "alerts")
    settings = PluginSettings(
        alerts=_alerts(alerts),
        sound_enabled=_bool(request, "sound"),
        record_journal=_bool(request, "recordJournal"),
        # The desktop application shows every chosen activity: the plugin's mode is kept
        display=replace(current.display, activities=_activities(request.get("activities"))),
    )
    language = request.get("language")
    if language not in LANGUAGES:
        raise SettingsError("language", f"not one of {LANGUAGES}")
    folder = request.get("journalFolder")
    if folder is not None and not isinstance(folder, str):
        raise SettingsError("journalFolder", "not a folder")
    folder = folder.strip() if folder else None
    if folder and not Path(folder).is_absolute():
        raise SettingsError("journalFolder", "not an absolute path")
    return settings, DesktopPreferences(str(language), folder or None)


def _mapping(request: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    value = request.get(field)
    if not isinstance(value, Mapping):
        raise SettingsError(field, "missing")
    return value


def _bool(request: Mapping[str, Any], field: str) -> bool:
    value = request.get(field)
    if not isinstance(value, bool):
        raise SettingsError(field, "not true or false")
    return value


def _percent(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= 100:
        raise SettingsError(field, "not a percentage from 0 to 100")
    return float(value)


def _alerts(alerts: Mapping[str, Any]) -> AlertSettings:
    known = {key for key, _ in MINEABLE}
    thresholds: dict[Commodity, float] = {}
    rows = alerts.get("thresholds")
    if not isinstance(rows, Sequence):
        raise SettingsError("thresholds", "missing")
    for row in rows:
        if not isinstance(row, Mapping) or row.get("commodity") not in known:
            raise SettingsError("thresholds", f"unknown commodity in {row!r}")
        key = str(row["commodity"])
        threshold = _percent(row.get("threshold"), f"threshold.{key}")
        if threshold is not None:
            thresholds[Commodity.from_symbol(key)] = threshold
    content = _CONTENTS.get(str(alerts.get("minimumContent")))
    if content is None:
        raise SettingsError("minimumContent", "not low, medium or high")
    cores = alerts.get("cores")
    if not isinstance(cores, bool):
        raise SettingsError("cores", "not true or false")
    return AlertSettings(
        thresholds=thresholds,
        minimum_content=content,
        minimum_remaining=_percent(alerts.get("minimumRemaining"), "minimumRemaining"),
        alert_on_cores=cores,
    )


def _activities(value: Any) -> tuple[Activity, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise SettingsError("activities", "not a list")
    try:
        chosen = tuple(Activity(item) for item in value)
    except ValueError as error:
        raise SettingsError("activities", str(error)) from error
    if not chosen:
        raise SettingsError("activities", "at least one activity is shown")
    return DisplaySettings(chosen).activities
