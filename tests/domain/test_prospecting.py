from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.journal import AsteroidProspected, ContentLevel, MaterialShare
from edrockmaster.domain.prospecting import (
    DEFAULT_ALERT_SETTINGS,
    DUPLICATE_WINDOW,
    AlertSettings,
    CommodityAlert,
    CoreAlert,
    ProspectingMonitor,
    ProspectorAlertRaised,
)

T0 = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
PAINITE = Commodity.from_symbol("painite")
PLATINUM = Commodity.from_symbol("platinum")
BAUXITE = Commodity.from_symbol("bauxite")
LTD = Commodity.from_symbol("lowtemperaturediamond")

SETTINGS = AlertSettings(
    thresholds={PAINITE: 25.0, PLATINUM: 20.0},
    minimum_content=ContentLevel.MEDIUM,
    minimum_remaining=None,
    alert_on_cores=True,
)


def asteroid(
    *shares: tuple[Commodity, float],
    content: ContentLevel = ContentLevel.HIGH,
    remaining: float | None = 100.0,
    motherlode: Commodity | None = None,
    seconds: float = 0,
) -> AsteroidProspected:
    return AsteroidProspected(
        at=T0 + timedelta(seconds=seconds),
        materials=tuple(MaterialShare(c, p) for c, p in shares),
        content=content,
        remaining=remaining,
        motherlode=motherlode,
    )


def test_commodity_above_its_threshold_raises_an_alert() -> None:
    raised = ProspectingMonitor(SETTINGS).evaluate(asteroid((PAINITE, 31.5), (BAUXITE, 50.0)))
    assert raised == ProspectorAlertRaised(
        at=T0,
        alerts=(CommodityAlert(commodity=PAINITE, proportion=31.5, threshold=25.0),),
    )


def test_threshold_is_inclusive() -> None:
    assert ProspectingMonitor(SETTINGS).evaluate(asteroid((PLATINUM, 20.0))) is not None


def test_commodity_below_its_threshold_is_silent() -> None:
    assert ProspectingMonitor(SETTINGS).evaluate(asteroid((PAINITE, 24.9))) is None


def test_commodity_without_threshold_is_silent() -> None:
    assert ProspectingMonitor(SETTINGS).evaluate(asteroid((BAUXITE, 90.0))) is None


def test_several_commodities_above_threshold_are_all_reported() -> None:
    raised = ProspectingMonitor(SETTINGS).evaluate(asteroid((PAINITE, 30.0), (PLATINUM, 22.0)))
    assert raised is not None
    assert {alert.commodity for alert in raised.alerts if isinstance(alert, CommodityAlert)} == {
        PAINITE,
        PLATINUM,
    }


@pytest.mark.parametrize(
    ("content", "alerted"),
    [
        (ContentLevel.HIGH, True),
        (ContentLevel.MEDIUM, True),
        (ContentLevel.LOW, False),
        (ContentLevel.UNKNOWN, False),
    ],
)
def test_minimum_content_level(content: ContentLevel, alerted: bool) -> None:
    raised = ProspectingMonitor(SETTINGS).evaluate(asteroid((PAINITE, 40.0), content=content))
    assert (raised is not None) is alerted


def test_unknown_content_passes_when_any_level_is_accepted() -> None:
    settings = AlertSettings(
        thresholds={PAINITE: 25.0},
        minimum_content=ContentLevel.LOW,
        minimum_remaining=None,
        alert_on_cores=True,
    )
    raised = ProspectingMonitor(settings).evaluate(
        asteroid((PAINITE, 40.0), content=ContentLevel.UNKNOWN)
    )
    assert raised is not None


@pytest.mark.parametrize(("remaining", "alerted"), [(100.0, True), (50.0, True), (49.9, False)])
def test_minimum_remaining_reserve(remaining: float, alerted: bool) -> None:
    settings = AlertSettings(
        thresholds={PAINITE: 25.0},
        minimum_content=ContentLevel.LOW,
        minimum_remaining=50.0,
        alert_on_cores=True,
    )
    raised = ProspectingMonitor(settings).evaluate(asteroid((PAINITE, 40.0), remaining=remaining))
    assert (raised is not None) is alerted


def test_unknown_remaining_reserve_does_not_block_alerts() -> None:
    settings = AlertSettings(
        thresholds={PAINITE: 25.0},
        minimum_content=ContentLevel.LOW,
        minimum_remaining=50.0,
        alert_on_cores=True,
    )
    assert ProspectingMonitor(settings).evaluate(asteroid((PAINITE, 40.0), remaining=None))


def test_core_raises_its_own_alert_whatever_the_filters() -> None:
    raised = ProspectingMonitor(SETTINGS).evaluate(
        asteroid((BAUXITE, 10.0), content=ContentLevel.LOW, motherlode=LTD)
    )
    assert raised == ProspectorAlertRaised(at=T0, alerts=(CoreAlert(commodity=LTD),))


def test_core_alerts_can_be_disabled() -> None:
    settings = AlertSettings(
        thresholds={},
        minimum_content=ContentLevel.LOW,
        minimum_remaining=None,
        alert_on_cores=False,
    )
    assert ProspectingMonitor(settings).evaluate(asteroid(motherlode=LTD)) is None


def test_core_and_commodity_alerts_together() -> None:
    raised = ProspectingMonitor(SETTINGS).evaluate(asteroid((PAINITE, 30.0), motherlode=LTD))
    assert raised is not None
    assert raised.alerts == (
        CoreAlert(commodity=LTD),
        CommodityAlert(commodity=PAINITE, proportion=30.0, threshold=25.0),
    )


def test_prospecting_the_same_asteroid_twice_alerts_once() -> None:
    monitor = ProspectingMonitor(SETTINGS)
    assert monitor.evaluate(asteroid((PAINITE, 30.0))) is not None
    assert monitor.evaluate(asteroid((PAINITE, 30.0), seconds=8)) is None


def test_same_composition_after_the_window_is_another_asteroid() -> None:
    monitor = ProspectingMonitor(SETTINGS)
    monitor.evaluate(asteroid((PAINITE, 30.0)))
    later = DUPLICATE_WINDOW.total_seconds() + 1
    assert monitor.evaluate(asteroid((PAINITE, 30.0), seconds=later)) is not None


def test_different_composition_right_after_is_another_asteroid() -> None:
    monitor = ProspectingMonitor(SETTINGS)
    monitor.evaluate(asteroid((PAINITE, 30.0)))
    assert monitor.evaluate(asteroid((PAINITE, 33.0), seconds=3)) is not None


def test_settings_can_be_replaced() -> None:
    monitor = ProspectingMonitor(SETTINGS)
    monitor.update_settings(
        AlertSettings(
            thresholds={BAUXITE: 10.0},
            minimum_content=ContentLevel.LOW,
            minimum_remaining=None,
            alert_on_cores=True,
        )
    )
    assert monitor.evaluate(asteroid((BAUXITE, 50.0))) is not None


def test_thresholds_must_be_percentages() -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        AlertSettings(
            thresholds={PAINITE: 120.0},
            minimum_content=ContentLevel.LOW,
            minimum_remaining=None,
            alert_on_cores=True,
        )


def test_default_settings_cover_valuable_laser_mining_commodities() -> None:
    keys = {commodity.key for commodity in DEFAULT_ALERT_SETTINGS.thresholds}
    assert {"platinum", "painite", "osmium", "palladium", "gold"} <= keys
    assert DEFAULT_ALERT_SETTINGS.alert_on_cores is True


def test_minimum_remaining_must_be_a_percentage() -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        AlertSettings(
            thresholds={},
            minimum_content=ContentLevel.LOW,
            minimum_remaining=-5.0,
            alert_on_cores=True,
        )


def test_settings_cannot_be_changed_through_the_original_mapping() -> None:
    thresholds = {PAINITE: 25.0}
    settings = AlertSettings(
        thresholds=thresholds,
        minimum_content=ContentLevel.LOW,
        minimum_remaining=None,
        alert_on_cores=True,
    )
    thresholds[PAINITE] = 1.0
    assert settings.thresholds[PAINITE] == 25.0
