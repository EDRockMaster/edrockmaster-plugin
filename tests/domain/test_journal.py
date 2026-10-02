from datetime import UTC, datetime

import pytest

from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.journal import (
    AsteroidCracked,
    AsteroidProspected,
    CargoChanged,
    CargoEjected,
    CommodityRefined,
    ContentLevel,
    GameLoaded,
    LeaveReason,
    LimpetKind,
    LimpetLaunched,
    MiningAreaLeft,
    RingEntered,
    parse_entry,
)

TS = "2026-10-02T12:00:00Z"
AT = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def test_prospected_asteroid_is_parsed() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "ProspectedAsteroid",
            "Materials": [
                {"Name": "Platinum", "Name_Localised": "Platine", "Proportion": 32.5},
                {"Name": "Painite", "Proportion": 7.25},
            ],
            "MotherlodeMaterial": "LowTemperatureDiamond",
            "MotherlodeMaterial_Localised": "Low Temperature Diamonds",
            "Content": "$AsteroidMaterialContent_High;",
            "Content_Localised": "Material Content: High",
            "Remaining": 100.0,
        }
    )
    assert isinstance(fact, AsteroidProspected)
    assert fact.at == AT
    assert fact.content is ContentLevel.HIGH
    assert fact.remaining == 100.0
    assert fact.motherlode == Commodity.from_symbol("lowtemperaturediamond")
    assert [(m.commodity.key, m.proportion) for m in fact.materials] == [
        ("platinum", 32.5),
        ("painite", 7.25),
    ]
    assert fact.materials[0].commodity.display_name == "Platine"


@pytest.mark.parametrize(
    ("content", "level"),
    [
        ("$AsteroidMaterialContent_High;", ContentLevel.HIGH),
        ("$AsteroidMaterialContent_Medium;", ContentLevel.MEDIUM),
        ("$AsteroidMaterialContent_Low;", ContentLevel.LOW),
        ("$Something_Else;", ContentLevel.UNKNOWN),
    ],
)
def test_content_level(content: str, level: ContentLevel) -> None:
    fact = parse_entry(
        {"timestamp": TS, "event": "ProspectedAsteroid", "Materials": [], "Content": content}
    )
    assert isinstance(fact, AsteroidProspected)
    assert fact.content is level


def test_prospected_asteroid_without_optional_fields() -> None:
    fact = parse_entry({"timestamp": TS, "event": "ProspectedAsteroid", "Materials": []})
    assert isinstance(fact, AsteroidProspected)
    assert fact.motherlode is None
    assert fact.remaining is None
    assert fact.content is ContentLevel.UNKNOWN


def test_refinement_is_parsed() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "MiningRefined",
            "Type": "$painite_name;",
            "Type_Localised": "Painite",
        }
    )
    assert fact == CommodityRefined(at=AT, commodity=Commodity.from_symbol("painite"))


@pytest.mark.parametrize(
    ("journal_type", "kind"),
    [
        ("Prospector", LimpetKind.PROSPECTOR),
        ("Collection", LimpetKind.COLLECTOR),
        ("Hatchbreaker", LimpetKind.OTHER),
    ],
)
def test_limpet_launch_is_parsed(journal_type: str, kind: LimpetKind) -> None:
    fact = parse_entry({"timestamp": TS, "event": "LaunchDrone", "Type": journal_type})
    assert fact == LimpetLaunched(at=AT, kind=kind)


def test_asteroid_cracked_is_parsed() -> None:
    fact = parse_entry({"timestamp": TS, "event": "AsteroidCracked", "Body": "Col 285 A Ring"})
    assert fact == AsteroidCracked(at=AT)


def test_entering_a_ring_is_parsed() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "SupercruiseExit",
            "StarSystem": "Col 285 Sector AB-C d1",
            "SystemAddress": 123456789,
            "Body": "Col 285 Sector AB-C d1 2 A Ring",
            "BodyType": "PlanetaryRing",
        }
    )
    assert fact == RingEntered(
        at=AT,
        system="Col 285 Sector AB-C d1",
        system_address=123456789,
        ring="Col 285 Sector AB-C d1 2 A Ring",
    )


def test_dropping_at_something_else_than_a_ring_is_ignored() -> None:
    entry = {"timestamp": TS, "event": "SupercruiseExit", "Body": "Station", "BodyType": "Station"}
    assert parse_entry(entry) is None


@pytest.mark.parametrize(
    ("event", "reason"),
    [
        ("SupercruiseEntry", LeaveReason.SUPERCRUISE),
        ("FSDJump", LeaveReason.JUMP),
        ("Docked", LeaveReason.DOCKED),
        ("Shutdown", LeaveReason.GAME_CLOSED),
        ("ShutDown", LeaveReason.GAME_CLOSED),
    ],
)
def test_leaving_the_mining_area(event: str, reason: LeaveReason) -> None:
    assert parse_entry({"timestamp": TS, "event": event}) == MiningAreaLeft(at=AT, reason=reason)


def test_cargo_snapshot_from_the_ship_is_parsed() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "Cargo",
            "Vessel": "Ship",
            "Count": 12,
            "Inventory": [
                {"Name": "painite", "Count": 10, "Stolen": 0},
                {"Name": "drones", "Name_Localised": "Limpet", "Count": 2, "Stolen": 0},
            ],
        }
    )
    assert isinstance(fact, CargoChanged)
    assert fact.total == 12
    assert fact.limpets == 2
    assert fact.tons_of(Commodity.from_symbol("painite")) == 10


def test_cargo_of_the_srv_is_ignored() -> None:
    assert parse_entry({"timestamp": TS, "event": "Cargo", "Vessel": "SRV", "Count": 0}) is None


def test_cargo_without_inventory_is_ignored() -> None:
    # EDMC normally attaches Cargo.json; without it there is nothing to learn
    assert parse_entry({"timestamp": TS, "event": "Cargo", "Vessel": "Ship", "Count": 3}) is None


def test_ejected_cargo_is_parsed() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "EjectCargo",
            "Type": "bromellite",
            "Count": 3,
            "Abandoned": True,
        }
    )
    assert fact == CargoEjected(at=AT, commodity=Commodity.from_symbol("bromellite"), count=3)


@pytest.mark.parametrize(("version", "live"), [("4.1.2.0", True), ("3.8.0.407", False)])
def test_game_loaded_tells_the_galaxy(version: str, live: bool) -> None:
    fact = parse_entry({"timestamp": TS, "event": "LoadGame", "gameversion": version})
    assert fact == GameLoaded(at=AT, game_version=version, is_live=live)


@pytest.mark.parametrize(
    "entry",
    [
        {"timestamp": TS, "event": "Music", "MusicTrack": "Exploration"},
        {"event": "MiningRefined", "Type": "$painite_name;"},
        {"timestamp": "not a date", "event": "MiningRefined", "Type": "$painite_name;"},
        {"timestamp": TS, "event": "MiningRefined"},
        {"timestamp": TS, "event": "LaunchDrone", "Type": 42},
        {"timestamp": TS, "event": "ProspectedAsteroid", "Materials": "oops"},
        {"timestamp": TS, "event": "ProspectedAsteroid", "Materials": [42]},
        {
            "timestamp": TS,
            "event": "ProspectedAsteroid",
            "Materials": [{"Name": "Painite", "Proportion": "high"}],
        },
        {"timestamp": TS, "event": "MiningRefined", "Type": "   "},
        {"timestamp": TS},
        {"timestamp": TS, "event": ["ProspectedAsteroid"]},
        {},
    ],
)
def test_unknown_or_malformed_entries_are_ignored(entry: dict[str, object]) -> None:
    assert parse_entry(entry) is None
