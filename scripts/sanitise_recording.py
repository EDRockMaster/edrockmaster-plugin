"""Turn a journal recording into a test fixture that is safe to publish.

The plugin repository is public. A raw recording holds personal data: the
commander's name and Frontier id, squadron, carrier, chat messages and other
players' names. This script keeps only the events the plugin reads, plus a few
harmless ones that prove unknown events are ignored, reduces ``LoadGame`` to
the game version and drops the commander's reputation, then refuses to write
anything if the commander's name or id is still present.

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
}
HARMLESS = {
    "Music",
    "ShieldState",
    "HeatWarning",
    "UnderAttack",
    "HullDamage",
    "StartJump",
    "Undocked",
    "DockingRequested",
    "DockingGranted",
    "RefuelAll",
    "RepairAll",
    "Repair",
    "BuyAmmo",
    "ReservoirReplenished",
}
LOAD_GAME_FIELDS = {"timestamp", "event", "gameversion", "build", "Horizons", "Odyssey"}
PERSONAL_FIELDS = {"Factions"}
"""Fields the plugin does not read that describe the commander (here: reputation per faction)."""


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


def sanitise(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept = []
    for record in records:
        entry = record["entry"]
        event = entry.get("event")
        if event not in READ_BY_THE_PLUGIN | HARMLESS:
            continue
        if event == "LoadGame":
            entry = {key: value for key, value in entry.items() if key in LOAD_GAME_FIELDS}
        entry = {key: value for key, value in entry.items() if key not in PERSONAL_FIELDS}
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
    leaks = sorted(identity for identity in identities(records) if identity in output)
    if leaks:
        print(f"refused: {len(leaks)} personal identifier(s) still present", file=sys.stderr)
        return 1
    target.write_text(output, encoding="utf-8")
    print(f"{len(kept)} of {len(records)} entries kept in {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
