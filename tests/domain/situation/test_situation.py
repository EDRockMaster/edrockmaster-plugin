from datetime import UTC, datetime

import pytest

from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.situation.journal import (
    GameLoaded,
    GameMode,
    Located,
    Ship,
    WingJoined,
    parse_entry,
)
from edrockmaster.domain.situation.situation import Situation, SituationChanged, SituationTracker

TS = "2026-10-08T23:10:17Z"
AT = datetime(2026, 10, 8, 23, 10, 17, tzinfo=UTC)

LOAD_GAME: Entry = {
    "event": "LoadGame",
    "Commander": "Nyx-Vela",
    "Ship": "PantherMkII",
    "Ship_Localised": "Panther Clipper Mk II",
    "ShipName": "",
    "ShipIdent": "",
    "GameMode": "Group",
    "Group": "Nyx-Vela",
}


def entry(**fields: object) -> Entry:
    return {"timestamp": TS, **fields}


def situation_after(*entries: Entry) -> Situation:
    tracker = SituationTracker()
    for raw in entries:
        fact = parse_entry({"timestamp": TS, **raw})
        if fact is not None:
            tracker.handle(fact)
    return tracker.situation


# The journal


def test_the_game_loaded() -> None:
    assert parse_entry(entry(**LOAD_GAME)) == GameLoaded(
        AT,
        "Nyx-Vela",
        Ship("PantherMkII", "Panther Clipper Mk II"),
        GameMode.GROUP,
        "Nyx-Vela",
    )


def test_a_group_name_only_in_a_private_group() -> None:
    fact = parse_entry(entry(event="LoadGame", GameMode="Open", Group="ignored"))
    assert isinstance(fact, GameLoaded)
    assert (fact.mode, fact.group, fact.ship) == (GameMode.OPEN, None, None)


def test_a_location_names_the_station_only_when_docked() -> None:
    docked = entry(event="Location", Docked=True, StationName="TZF-66Z", StarSystem="Col 359")
    assert parse_entry(docked) == Located(AT, "Col 359", "TZF-66Z")
    in_space = entry(event="Location", Docked=False, StationName="X", StarSystem="Sol")
    assert parse_entry(in_space) == Located(AT, "Sol", None)


def test_wing_members_as_names_or_objects() -> None:
    joined = entry(event="WingJoin", Others=["Cmdr A", {"Name": "Cmdr B"}, " ", 3])
    assert parse_entry(joined) == WingJoined(AT, ("Cmdr A", "Cmdr B"))


@pytest.mark.parametrize(
    "raw",
    [
        {"event": "Commander", "Name": ""},
        {"event": "Docked", "StationName": ""},
        {"event": "WingAdd"},
        {"event": "FSDJump"},
        {"event": "Music"},
    ],
)
def test_irrelevant_or_malformed_entries_are_ignored(raw: Entry) -> None:
    assert parse_entry(entry(**raw)) is None


# The situation


def test_unknown_until_the_journal_tells() -> None:
    assert situation_after() == Situation()


def test_who_where_in_which_ship_and_mode() -> None:
    situation = situation_after(
        {"event": "Commander", "Name": "Nyx-Vela"},
        LOAD_GAME,
        {"event": "Location", "Docked": True, "StationName": "TZF-66Z", "StarSystem": "Col 359"},
    )
    assert situation == Situation(
        commander="Nyx-Vela",
        ship=Ship("PantherMkII", "Panther Clipper Mk II"),
        system="Col 359",
        station="TZF-66Z",
        mode=GameMode.GROUP,
        group="Nyx-Vela",
        game_running=True,
    )


def test_travels() -> None:
    start = {"event": "Location", "Docked": True, "StationName": "TZF-66Z", "StarSystem": "Col 359"}
    situation = situation_after(start, {"event": "Undocked", "StationName": "TZF-66Z"})
    assert (situation.system, situation.station) == ("Col 359", None)
    situation = situation_after(
        start,
        {"event": "Undocked"},
        {"event": "FSDJump", "StarSystem": "Col 285"},
        {"event": "Docked", "StationName": "Amano Terminal", "StarSystem": "Col 285"},
    )
    assert (situation.system, situation.station) == ("Col 285", "Amano Terminal")
    # Leaving a station by a jump of a carrier, or a supercruise exit, keeps the system right
    situation = situation_after(start, {"event": "CarrierJump", "StarSystem": "Sol"})
    assert (situation.system, situation.station) == ("Sol", None)


def test_a_ship_bought_or_swapped_keeps_its_name_in_the_game_s_language() -> None:
    situation = situation_after(
        LOAD_GAME,
        {"event": "ShipyardSwap", "ShipType": "mamba", "ShipType_Localised": "Mamba"},
        {"event": "Loadout", "Ship": "mamba", "ShipName": "Rocky", "ShipIdent": "RM-01"},
    )
    assert situation.ship == Ship("mamba", "Mamba", "Rocky", "RM-01")
    # The Loadout of a ship seen before gets its name back
    situation = situation_after(
        LOAD_GAME, {"event": "Loadout", "Ship": "pantherMkII", "ShipName": "Clip"}
    )
    assert situation.ship == Ship("pantherMkII", "Panther Clipper Mk II", "Clip")


def test_the_loadout_gives_the_cargo_capacity() -> None:
    loadout = {"event": "Loadout", "Ship": "type9", "ShipName": "", "CargoCapacity": 720}
    situation = situation_after(LOAD_GAME, loadout)
    assert situation.ship is not None
    assert situation.ship.cargo_capacity == 720
    # A ship swapped is not known until its Loadout
    swapped = {"event": "ShipyardSwap", "ShipType": "mamba", "ShipType_Localised": "Mamba"}
    swapped_ship = situation_after(LOAD_GAME, loadout, swapped).ship
    assert swapped_ship is not None
    assert swapped_ship.cargo_capacity is None
    # Renamed, it keeps its capacity
    renamed = {"event": "SetUserShipName", "UserShipName": "Nova", "UserShipId": "NV-1"}
    renamed_ship = situation_after(LOAD_GAME, loadout, renamed).ship
    assert renamed_ship is not None
    assert renamed_ship.cargo_capacity == 720


def test_renaming_the_ship() -> None:
    renamed = {"event": "SetUserShipName", "UserShipName": "Nova", "UserShipId": "NV-1"}
    assert situation_after(renamed).ship is None  # no ship known yet
    situation = situation_after(LOAD_GAME, renamed)
    assert situation.ship == Ship("PantherMkII", "Panther Clipper Mk II", "Nova", "NV-1")


def test_on_foot_and_back() -> None:
    assert situation_after(LOAD_GAME, {"event": "Disembark"}).on_foot
    assert not situation_after(LOAD_GAME, {"event": "Disembark"}, {"event": "Embark"}).on_foot


def test_wing() -> None:
    joined = {"event": "WingJoin", "Others": ["Cmdr A"]}
    assert situation_after(joined, {"event": "WingAdd", "Name": "Cmdr B"}).wing == (
        "Cmdr A",
        "Cmdr B",
    )
    assert situation_after(joined, {"event": "WingAdd", "Name": "Cmdr A"}).wing == ("Cmdr A",)
    assert situation_after(joined, {"event": "WingLeave"}).wing == ()


def test_closing_the_game_keeps_the_last_situation() -> None:
    situation = situation_after(
        LOAD_GAME, {"event": "WingJoin", "Others": ["Cmdr A"]}, {"event": "Shutdown"}
    )
    assert not situation.game_running
    assert situation.commander == "Nyx-Vela"
    assert situation.wing == ()
    assert situation_after(LOAD_GAME, {"event": "Shutdown"}, LOAD_GAME).game_running


def test_a_change_is_notified_once() -> None:
    tracker = SituationTracker()
    fact = parse_entry(entry(event="FSDJump", StarSystem="Sol"))
    assert fact is not None
    [changed] = tracker.handle(fact)
    assert changed == SituationChanged(Situation(system="Sol"))
    assert tracker.handle(fact) == []


# The game loaded on foot, and ship types the journal does not name


def test_the_game_loaded_on_foot_names_a_suit_not_a_ship() -> None:
    on_foot = entry(
        **{**LOAD_GAME, "Ship": "UtilitySuit_Class2", "Ship_Localised": "$UtilitySuit_Class1_Name;"}
    )
    fact = parse_entry(on_foot)
    assert isinstance(fact, GameLoaded)
    assert (fact.ship, fact.on_foot) == (None, True)
    situation = situation_after(on_foot)
    assert situation.ship is None
    assert situation.on_foot


def test_a_ship_type_the_journal_does_not_name_takes_its_known_name() -> None:
    tracker = SituationTracker({"panthermkii": "Panther Clipper MkII"})
    loadout = {"event": "Loadout", "Ship": "panthermkii", "ShipName": "", "ShipIdent": "NY-07P"}
    for raw in (loadout,):
        fact = parse_entry({"timestamp": TS, **raw})
        assert fact is not None
        tracker.handle(fact)
    ship = tracker.situation.ship
    assert ship is not None
    assert (ship.type_name, ship.ident) == ("Panther Clipper MkII", "NY-07P")
    # The game's own name, once the journal gives it, comes first
    loaded = parse_entry(entry(**LOAD_GAME))
    assert loaded is not None
    tracker.handle(loaded)
    fact = parse_entry({"timestamp": TS, **loadout})
    assert fact is not None
    tracker.handle(fact)
    ship = tracker.situation.ship
    assert ship is not None
    assert ship.type_name == "Panther Clipper Mk II"
