"""The recording sanitiser: what a public fixture may and may not contain."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sanitise_recording.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sanitise_recording", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sanitiser = load_script()
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


def test_reputation_is_dropped_from_locations() -> None:
    factions = [{"Name": "X", "MyReputation": 42.0}]
    [entry] = kept(record(event="Location", StarSystem="Sol", Factions=factions))
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
