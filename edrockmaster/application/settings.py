"""The player's settings, as one immutable object."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from edrockmaster.application.activity import Activity
from edrockmaster.domain.mining.prospecting import DEFAULT_ALERT_SETTINGS, AlertSettings


class DisplayMode(Enum):
    """How the panel shows the activities (ADR 0013)."""

    LAST_ACTIVE = "last_active"
    """One activity: the one that progressed last."""
    STACKED = "stacked"
    """Each activity shown has its own block."""


@dataclass(frozen=True, slots=True)
class DisplaySettings:
    activities: tuple[Activity, ...] = tuple(Activity)
    """The activities the panel may show, in display order (the order of ``Activity``)."""
    mode: DisplayMode = DisplayMode.LAST_ACTIVE

    def __post_init__(self) -> None:
        if not self.activities:
            raise ValueError("the panel shows at least one activity")
        chosen = set(self.activities)
        object.__setattr__(self, "activities", tuple(a for a in Activity if a in chosen))


@dataclass(frozen=True, slots=True)
class PluginSettings:
    """Everything the player can change in the preferences tab."""

    alerts: AlertSettings
    sound_enabled: bool
    record_journal: bool
    display: DisplaySettings = field(default_factory=DisplaySettings)


DEFAULT_SETTINGS = PluginSettings(
    alerts=DEFAULT_ALERT_SETTINGS,
    sound_enabled=True,
    record_journal=False,
)
