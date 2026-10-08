"""The recording sanitiser: what a public fixture may and may not contain."""

import json
from pathlib import Path
from typing import Any

import pytest

from tests.scripts import load_script

sanitiser = load_script("sanitise_recording")
TS = "2026-10-03T12:00:00Z"


def record(**entry: Any) -> dict[str, Any]:
    return {"is_beta": False, "entry": {"timestamp": TS, **entry}}


def kept(*records: dict[str, Any]) -> list[dict[str, Any]]:
    return [r["entry"] for r in sanitiser.sanitise(list(records))]


def test_events_not_read_by_the_plugin_are_dropped() -> None:
    assert (
        kept(
            record(event="ReceiveText", From="Someone", Message="hello"),
            record(event="Friends", Name="Someone", Status="Online"),
            record(event="Commander", Name="Cmdr", FID="F123"),
            record(event="SquadronStartup", SquadronName="Squad"),
        )
        == []
    )


def test_load_game_is_reduced_to_the_game_version() -> None:
    [entry] = kept(record(event="LoadGame", Commander="Cmdr", FID="F123", gameversion="4.4.1.1"))
    assert entry == {"timestamp": TS, "event": "LoadGame", "gameversion": "4.4.1.1"}


@pytest.mark.parametrize("event", ["Location", "FSDJump", "StartUp"])
def test_reputation_is_dropped_from_locations(event: str) -> None:
    factions = [{"Name": "X", "MyReputation": 42.0}]
    [entry] = kept(record(event=event, StarSystem="Sol", Factions=factions))
    assert "Factions" not in entry
    assert entry["StarSystem"] == "Sol"


def test_redeemed_vouchers_keep_their_factions() -> None:
    paid = [{"Faction": "Federation", "Amount": 1000}]
    [entry] = kept(record(event="RedeemVoucher", Type="bounty", Amount=1000, Factions=paid))
    assert entry["Factions"] == paid


def test_pilot_names_of_targets_are_dropped() -> None:
    [entry] = kept(
        record(
            event="Bounty",
            PilotName="$cmdr_decorate:#name=Someone;",
            PilotName_Localised="Cmdr Someone",
            TotalReward=1000,
        )
    )
    assert "PilotName" not in entry
    assert "PilotName_Localised" not in entry
    assert entry["TotalReward"] == 1000


def test_victims_of_crimes_are_dropped() -> None:
    [entry] = kept(record(event="CommitCrime", CrimeType="murder", Victim="Someone", Bounty=5))
    assert "Victim" not in entry
    assert (entry["CrimeType"], entry["Bounty"]) == ("murder", 5)


def test_combat_sites_are_kept() -> None:
    [entry] = kept(record(event="SupercruiseDestinationDrop", Type="$Warzone_PointRace_High;"))
    assert entry["Type"] == "$Warzone_PointRace_High;"


@pytest.mark.parametrize(
    "entry",
    [
        {"event": "ApproachSettlement", "Name": "Pak's Habitat"},
        {"event": "BookDropship", "Retreat": False, "DestinationLocation": "Pak's Habitat"},
        {"event": "DropshipDeploy", "Body": "Redonesses A 1", "OnPlanet": True},
        {"event": "Disembark", "OnPlanet": True, "OnStation": False},
        {"event": "Embark", "Taxi": True, "OnStation": True},
    ],
)
def test_moves_on_foot_are_kept(entry: dict[str, Any]) -> None:
    assert kept(record(**entry)) == [{"timestamp": TS, **entry}]


def test_trades_are_kept() -> None:
    purchase = {"event": "MarketBuy", "MarketID": 42, "Type": "palladium", "Count": 1}
    sale = {"event": "MarketSell", "MarketID": 42, "Type": "palladium", "AvgPricePaid": 4853}
    assert kept(record(**purchase), record(**sale)) == [
        {"timestamp": TS, **purchase},
        {"timestamp": TS, **sale},
    ]


def test_trades_at_a_fleet_carrier_are_anonymised() -> None:
    [_, purchase] = kept(
        record(event="Docked", StationName="TZF-66Z", StationType="FleetCarrier", MarketID=37),
        record(event="MarketBuy", MarketID=37, Type="tritium", Count=1),
    )
    assert purchase["MarketID"] == 0


def test_killers_are_dropped_from_deaths() -> None:
    [entry] = kept(
        record(
            event="Died",
            KillerName="Cmdr Someone",
            KillerShip="anaconda",
            KillerRank="Elite",
            Killers=[{"Name": "Cmdr Other", "Ship": "fdl", "Rank": "Elite"}],
        )
    )
    assert entry == {"timestamp": TS, "event": "Died", "KillerShip": "anaconda"}


CARRIER = record(
    event="CarrierStats", CarrierID=3700000000, Callsign="ABC-12Q", Name="[TAG] Somebody's Home"
)


def test_fleet_carriers_are_anonymised() -> None:
    records = [
        CARRIER,
        record(event="SupercruiseDestinationDrop", Type="[TAG] Somebody's Home ABC-12Q"),
        record(
            event="Docked",
            StationName="ABC-12Q",
            StationType="FleetCarrier",
            MarketID=3700000000,
            StarSystem="Sol",
        ),
    ]
    drop, docked = kept(*records)
    assert drop["Type"] == "Fleet carrier"
    assert (docked["StationName"], docked["MarketID"]) == ("Fleet carrier", 0)
    assert docked["StarSystem"] == "Sol"


def test_other_players_fleet_carriers_are_anonymised_too() -> None:
    docked = record(event="Docked", StationName="XYZ-987", StationType="FleetCarrier", MarketID=1)
    undocked = record(event="Undocked", StationName="XYZ-987", MarketID=1)
    assert [entry["StationName"] for entry in kept(docked, undocked)] == ["Fleet carrier"] * 2


def test_refuses_to_write_when_the_commander_is_still_named(tmp_path: Path) -> None:
    source = tmp_path / "recording.jsonl"
    target = tmp_path / "fixture.jsonl"
    records = [
        record(event="Commander", Name="Nobody", FID="F123"),
        record(event="Docked", StationName="Nobody's Rest"),
    ]
    source.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    assert sanitiser.main([str(source), str(target)]) == 1
    assert not target.exists()


def test_carriers_are_anonymised_in_any_field(tmp_path: Path) -> None:
    source = tmp_path / "recording.jsonl"
    target = tmp_path / "fixture.jsonl"
    records = [CARRIER, record(event="Music", MusicTrack="ABC-12Q")]
    source.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    assert sanitiser.main([str(source), str(target)]) == 0
    assert "ABC-12Q" not in target.read_text()


def test_writes_the_fixture(tmp_path: Path) -> None:
    source = tmp_path / "recording.jsonl"
    target = tmp_path / "fixture.jsonl"
    records = [record(event="Commander", Name="Nobody", FID="F123"), record(event="Music")]
    source.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    assert sanitiser.main([str(source), str(target)]) == 0
    assert [json.loads(line)["entry"]["event"] for line in target.read_text().splitlines()] == [
        "Music"
    ]


def test_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert sanitiser.main([]) == 2
    assert "Usage" in capsys.readouterr().err


@pytest.mark.parametrize(
    "entry",
    [
        {"event": "Materials", "Raw": [{"Name": "iron", "Count": 3}], "Manufactured": []},
        {"event": "MaterialCollected", "Category": "Raw", "Name": "iron", "Count": 3},
        {"event": "MaterialTrade", "Paid": {"Material": "iron"}, "Received": {"Material": "zinc"}},
        {
            "event": "EngineerCraft",
            "Engineer": "Marco Qwent",
            "EngineerID": 300200,
            "BlueprintName": "PowerDistributor_HighCapacity",
            "Level": 1,
            "Ingredients": [{"Name": "sulphur", "Count": 1}],
        },
        {"event": "EngineerProgress", "Engineer": "Marco Qwent", "Progress": "Unlocked"},
    ],
)
def test_engineering_is_kept(entry: dict[str, Any]) -> None:
    assert kept(record(**entry)) == [{"timestamp": TS, **entry}]


def test_missions_are_reduced_to_their_materials() -> None:
    reward = [{"Name": "polonium", "Count": 3}]
    mission = record(
        event="MissionCompleted",
        Faction="Some Faction",
        Name="Mission_Delivery",
        PassengerName="Someone",
        MaterialsReward=reward,
    )
    assert kept(mission) == [
        {"timestamp": TS, "event": "MissionCompleted", "MaterialsReward": reward}
    ]


def test_load_game_keeps_the_ship_type_and_the_game_mode() -> None:
    loaded = record(
        event="LoadGame",
        Commander="Cmdr",
        FID="F123",
        Ship="PantherMkII",
        Ship_Localised="Panther Clipper Mk II",
        ShipName="My ship",
        ShipIdent="MY-01",
        GameMode="Group",
        Group="A private group",
        gameversion="4.4.1.1",
    )
    assert kept(loaded) == [
        {
            "timestamp": TS,
            "event": "LoadGame",
            "Ship": "PantherMkII",
            "Ship_Localised": "Panther Clipper Mk II",
            "GameMode": "Group",
            "gameversion": "4.4.1.1",
        }
    ]


def test_a_loadout_is_reduced_to_the_ship_type() -> None:
    loadout = record(event="Loadout", Ship="mamba", ShipName="My ship", Modules=[{"Slot": "x"}])
    assert kept(loadout) == [{"timestamp": TS, "event": "Loadout", "Ship": "mamba"}]


def test_wingmates_get_neutral_names() -> None:
    entries = kept(
        record(event="WingJoin", Others=["Cmdr Alice", {"Name": "Cmdr Bob"}]),
        record(event="WingAdd", Name="Cmdr Carol"),
        record(event="WingAdd", Name="Cmdr Alice"),
        record(event="WingLeave"),
    )
    assert entries == [
        {"timestamp": TS, "event": "WingJoin", "Others": ["Wingmate 1", {"Name": "Wingmate 2"}]},
        {"timestamp": TS, "event": "WingAdd", "Name": "Wingmate 3"},
        {"timestamp": TS, "event": "WingAdd", "Name": "Wingmate 1"},
        {"timestamp": TS, "event": "WingLeave"},
    ]


def test_refuses_to_write_when_a_wingmate_is_still_named(tmp_path: Path) -> None:
    source = tmp_path / "raw.jsonl"
    lines = [
        record(event="WingAdd", Name="Cmdr Alice"),
        # Not read by the plugin, so dropped; but a kept event naming her would leak
        record(event="Docked", StationName="Cmdr Alice's place", MarketID=1),
    ]
    source.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    assert sanitiser.main([str(source), str(tmp_path / "fixture.jsonl")]) == 1
