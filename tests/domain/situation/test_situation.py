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
