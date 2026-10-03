"""The player's settings, as one immutable object."""

from __future__ import annotations

from dataclasses import dataclass

from edrockmaster.domain.mining.prospecting import DEFAULT_ALERT_SETTINGS, AlertSettings


@dataclass(frozen=True, slots=True)
class PluginSettings:
    """Everything the player can change in the preferences tab."""

    alerts: AlertSettings
    sound_enabled: bool
    record_journal: bool


DEFAULT_SETTINGS = PluginSettings(
    alerts=DEFAULT_ALERT_SETTINGS,
    sound_enabled=True,
    record_journal=False,
)
