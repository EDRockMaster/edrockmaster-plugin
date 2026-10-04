import pytest

from edrockmaster.domain.combat.sites import SiteType, combat_site


@pytest.mark.parametrize(
    ("signal", "site"),
    [
        # seen on arrival in the recording of 4 October 2026 (Iyakajauja), or in the scan
        # of the system (FSSSignalDiscovered), which uses the same identifiers
        ("$Warzone_PointRace_Low:#index=1;", SiteType.CONFLICT_ZONE_LOW),
        ("$Warzone_PointRace_Med:#index=1;", SiteType.CONFLICT_ZONE_MEDIUM),
        ("$Warzone_PointRace_High:#index=1;", SiteType.CONFLICT_ZONE_HIGH),
        ("$MULTIPLAYER_SCENARIO77_TITLE;", SiteType.RES_LOW),
        ("$MULTIPLAYER_SCENARIO14_TITLE;", SiteType.RES),
        ("$MULTIPLAYER_SCENARIO78_TITLE;", SiteType.RES_HIGH),
        ("$MULTIPLAYER_SCENARIO79_TITLE;", SiteType.RES_HAZARDOUS),
        ("$MULTIPLAYER_SCENARIO42_TITLE;", SiteType.NAV_BEACON),
    ],
)
def test_known_combat_sites(signal: str, site: SiteType) -> None:
    assert combat_site(signal) is site


def test_identifiers_are_matched_regardless_of_case() -> None:
    assert combat_site("$warzone_pointrace_high:#index=2;") is SiteType.CONFLICT_ZONE_HIGH


@pytest.mark.parametrize(
    "signal",
    [
        "Tan Depot",  # a station
        "$USS_HighGradeEmissions;",  # a signal source
        "$MULTIPLAYER_SCENARIO80_TITLE;",  # compromised beacon: not confirmed yet (ADR 0013)
        "",
    ],
)
def test_other_destinations_are_not_combat_sites(signal: str) -> None:
    assert combat_site(signal) is None
