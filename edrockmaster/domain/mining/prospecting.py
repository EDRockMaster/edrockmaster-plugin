"""Prospector alerts: which prospected asteroids deserve the player's attention."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType

from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.mining.journal import AsteroidProspected, ContentLevel

DUPLICATE_WINDOW = timedelta(seconds=60)
"""Prospecting an identical asteroid again within this window does not alert twice."""

_CONTENT_RANK = {
    ContentLevel.UNKNOWN: 0,
    ContentLevel.LOW: 1,
    ContentLevel.MEDIUM: 2,
    ContentLevel.HIGH: 3,
}


@dataclass(frozen=True, slots=True)
class AlertSettings:
    """What the player wants to be alerted about.

    ``thresholds`` maps a commodity to the minimum proportion, in percent, that
    raises an alert. ``minimum_content`` set to ``LOW`` accepts every asteroid,
    including those whose content level is unknown.
    """

    thresholds: Mapping[Commodity, float]
    minimum_content: ContentLevel
    minimum_remaining: float | None
    alert_on_cores: bool

    def __post_init__(self) -> None:
        for commodity, threshold in self.thresholds.items():
            if not 0.0 <= threshold <= 100.0:
                raise ValueError(f"threshold for {commodity.key} must be between 0 and 100")
        if self.minimum_remaining is not None and not 0.0 <= self.minimum_remaining <= 100.0:
            raise ValueError("minimum remaining reserve must be between 0 and 100")
        # Freeze the mapping so that the settings stay immutable
        object.__setattr__(self, "thresholds", MappingProxyType(dict(self.thresholds)))


def _thresholds(**percent: float) -> dict[Commodity, float]:
    return {Commodity.from_symbol(key): value for key, value in percent.items()}


DEFAULT_ALERT_SETTINGS = AlertSettings(
    thresholds=_thresholds(
        platinum=20.0,
        painite=25.0,
        osmium=25.0,
        palladium=25.0,
        gold=25.0,
        lowtemperaturediamond=20.0,
    ),
    minimum_content=ContentLevel.LOW,
    minimum_remaining=None,
    alert_on_cores=True,
)


@dataclass(frozen=True, slots=True)
class CommodityAlert:
    commodity: Commodity
    proportion: float
    threshold: float


@dataclass(frozen=True, slots=True)
class CoreAlert:
    commodity: Commodity


type Alert = CoreAlert | CommodityAlert


@dataclass(frozen=True, slots=True)
class ProspectorAlertRaised:
    at: datetime
    alerts: tuple[Alert, ...]


class ProspectingMonitor:
    """Evaluates every prospected asteroid against the player's alert settings."""

    def __init__(self, settings: AlertSettings) -> None:
        self._settings = settings
        self._last: tuple[object, datetime] | None = None

    def update_settings(self, settings: AlertSettings) -> None:
        self._settings = settings

    def evaluate(self, asteroid: AsteroidProspected) -> ProspectorAlertRaised | None:
        if self._is_duplicate(asteroid):
            return None
        alerts: list[Alert] = []
        if asteroid.motherlode is not None and self._settings.alert_on_cores:
            alerts.append(CoreAlert(commodity=asteroid.motherlode))
        if self._passes_filters(asteroid):
            alerts.extend(self._commodity_alerts(asteroid))
        return ProspectorAlertRaised(at=asteroid.at, alerts=tuple(alerts)) if alerts else None

    def _is_duplicate(self, asteroid: AsteroidProspected) -> bool:
        signature = (asteroid.materials, asteroid.content, asteroid.motherlode)
        previous, self._last = self._last, (signature, asteroid.at)
        if previous is None:
            return False
        previous_signature, previous_at = previous
        return previous_signature == signature and asteroid.at - previous_at <= DUPLICATE_WINDOW

    def _passes_filters(self, asteroid: AsteroidProspected) -> bool:
        settings = self._settings
        if settings.minimum_content is not ContentLevel.LOW and (
            _CONTENT_RANK[asteroid.content] < _CONTENT_RANK[settings.minimum_content]
        ):
            return False
        return not (
            settings.minimum_remaining is not None
            and asteroid.remaining is not None
            and asteroid.remaining < settings.minimum_remaining
        )

    def _commodity_alerts(self, asteroid: AsteroidProspected) -> list[CommodityAlert]:
        thresholds = self._settings.thresholds
        return [
            CommodityAlert(share.commodity, share.proportion, thresholds[share.commodity])
            for share in asteroid.materials
            if share.commodity in thresholds and share.proportion >= thresholds[share.commodity]
        ]
