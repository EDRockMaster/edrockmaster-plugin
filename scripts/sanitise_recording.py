"""Turn a journal recording into a test fixture that is safe to publish.

The plugin repository is public. A raw recording holds personal data: the
commander's name and Frontier id, squadron, carrier, chat messages and other
players' names. This script keeps only the events the plugin reads, plus a few
harmless ones that prove unknown events are ignored, reduces ``LoadGame`` to
the game version and ``MissionCompleted`` to its materials reward, drops the
commander's reputation, targets' pilot names, crime victims and the
commander's killers, replaces every fleet carrier (name,
callsign, id) with a neutral value, then refuses to write anything if the
commander's name or id, or a carrier, is still present.

Usage: python3 scripts/sanitise_recording.py <recording.jsonl> <fixture.jsonl>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

READ_BY_THE_PLUGIN = {
    # mining
    "ProspectedAsteroid",
    "MiningRefined",
    "LaunchDrone",
    "AsteroidCracked",
    "SupercruiseExit",
    "SupercruiseEntry",
    "FSDJump",
    "Docked",
    "Shutdown",
    "ShutDown",
    "Cargo",
    "EjectCargo",
    "MarketSell",
    "LoadGame",
    "Location",
    "StartUp",
    # bounty hunting
    "Bounty",
    "FactionKillBond",
    "CapShipBond",
    "RedeemVoucher",
    "Died",
    "CommunityGoal",
    # combat (ADR 0013)
    "SupercruiseDestinationDrop",
    "Undocked",
    "StartJump",
    "CommitCrime",
    # combat on foot, conflict zones the journal does not name (ADR 0015)
    "ApproachSettlement",
    "BookDropship",
    "DropshipDeploy",
    "Disembark",
    "Embark",
    # trade (ADR 0014)
    "MarketBuy",
    # fleet carrier transfers (ADR 0019)
    "CargoTransfer",
    # engineering (ADR 0017)
    "Materials",
    "MaterialCollected",
    "MaterialDiscarded",
    "MaterialTrade",
    "Synthesis",
    "TechnologyBroker",
    "EngineerContribution",
    "ScientificResearch",
    "MissionCompleted",
    "EngineerCraft",
    "EngineerProgress",
}
HARMLESS = {
    "Music",
    "ShieldState",
    "HeatWarning",
    "UnderAttack",
    "HullDamage",
    "DockingRequested",
    "DockingGranted",
    "RefuelAll",
    "RepairAll",
    "Repair",
    "BuyAmmo",
    "ReservoirReplenished",
}
REDUCED = {
    "LoadGame": {"timestamp", "event", "gameversion", "build", "Horizons", "Odyssey"},
    # a mission names factions, targets, passengers: only its materials matter
    "MissionCompleted": {"timestamp", "event", "MaterialsReward"},
}
PERSONAL_FIELDS = {
    # the commander's reputation with each faction of the system
    "Location": {"Factions"},
    "FSDJump": {"Factions"},
    "StartUp": {"Factions"},
    # the pilot of a target: another commander when the target is a player
    "Bounty": {"PilotName", "PilotName_Localised"},
    # the victim of a crime: may be another commander
    "CommitCrime": {"Victim", "Victim_Localised"},
    # the killers of the commander: other commanders, in player versus player
    "Died": {"KillerName", "KillerName_Localised", "KillerRank", "Killers"},
}
"""Fields the plugin does not read that describe people, per event. Per event: the same
name elsewhere may be needed (``RedeemVoucher.Factions`` is what was redeemed)."""


def identities(records: list[dict[str, Any]]) -> set[str]:
    """The commander's name and Frontier id, as the recording states them."""
    found = set()
    for record in records:
        entry = record["entry"]
        if entry.get("event") in ("Commander", "LoadGame"):
            for key in ("Name", "Commander", "FID"):
                if isinstance(entry.get(key), str) and entry[key]:
                    found.add(entry[key])
    return found


FLEET_CARRIER = "Fleet carrier"
CARRIER_EVENTS = {"CarrierStats", "CarrierLocation", "CarrierJumpRequest", "CarrierBuy"}


def carriers(records: list[dict[str, Any]]) -> tuple[set[str], set[int]]:
    """Names, callsigns and ids of the fleet carriers the recording mentions."""
    names: set[str] = set()
    ids: set[int] = set()
    for record in records:
        entry = record["entry"]
        if entry.get("event") in CARRIER_EVENTS:
            names |= {entry[key] for key in ("Callsign", "Name") if isinstance(entry.get(key), str)}
            if isinstance(entry.get("CarrierID"), int):
                ids.add(entry["CarrierID"])
        if entry.get("StationType") == "FleetCarrier":
            if isinstance(entry.get("StationName"), str):
                names.add(entry["StationName"])
            if isinstance(entry.get("MarketID"), int):
                ids.add(entry["MarketID"])
    return {name for name in names if name}, ids


def anonymise(value: Any, names: set[str], ids: set[int]) -> Any:
    """Replace every value naming a carrier: a whole text, so no tag or name is left."""
    if isinstance(value, str):
        return FLEET_CARRIER if any(name in value for name in names) else value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return 0 if value in ids else value
    if isinstance(value, list):
        return [anonymise(item, names, ids) for item in value]
    if isinstance(value, dict):
        return {key: anonymise(item, names, ids) for key, item in value.items()}
    return value


def sanitise(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names, ids = carriers(records)
    kept = []
    for record in records:
        entry = record["entry"]
        event = entry.get("event")
        if event not in READ_BY_THE_PLUGIN | HARMLESS:
            continue
        if event in REDUCED:
            entry = {key: value for key, value in entry.items() if key in REDUCED[event]}
        personal = PERSONAL_FIELDS.get(event, set())
        entry = {key: value for key, value in entry.items() if key not in personal}
        entry = anonymise(entry, names, ids)
        kept.append({"is_beta": record["is_beta"], "entry": entry})
    return kept


def main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    source, target = Path(arguments[0]), Path(arguments[1])
    lines = source.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    kept = sanitise(records)
    output = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in kept)
    names, ids = carriers(records)
    personal = identities(records) | names | {str(carrier_id) for carrier_id in ids}
    leaks = sorted(identity for identity in personal if identity in output)
    if leaks:
        print(f"refused: {len(leaks)} personal identifier(s) still present", file=sys.stderr)
        return 1
    target.write_text(output, encoding="utf-8")
    print(f"{len(kept)} of {len(records)} entries kept in {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
