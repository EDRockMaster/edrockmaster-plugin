"""Write the demo journal of the desktop application from the published fixtures.

The demo mode (``--demo``) replays this journal so that screenshots, for the
Microsoft Store or the documentation, show the application at work without a
player's name. It is a mining session in a resource extraction site, with its
combat bonds, from ``tests/fixtures/`` (already free of personal data), under
the fictional Commander Jameson in Open play, with the materials, engineers and
collected materials of the engineering fixture. It stops while the commander is
still mining in the ring, and the application moves its timestamps so that it
ends when the demo starts: the sessions are running.

Usage: python3 scripts/make_demo_journal.py [demo journal]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
SESSION = FIXTURES / "capricorni-iyakajauja-zones-mining-res-2026-10-04.jsonl"
ENGINEERING = FIXTURES / "engineering-power-distributor-2026-10-08.jsonl"
DEMO_JOURNAL = ROOT / "edrockmaster" / "desktop" / "demo_journal.jsonl"

COMMANDER = "Jameson"
SHIP = {
    "Ship": "python",
    "Ship_Localised": "Python",
    "ShipName": "Rock Hound",
    "ShipIdent": "ED-01",
}
ENGINEERING_EVENTS = ("Materials", "EngineerProgress")
COLLECTED = "MaterialCollected"
DROPPED = {"StartUp"}
"""Written by EDMC, which recorded the fixtures, not by the game."""


def _entries(fixture: Path) -> list[dict[str, Any]]:
    lines = fixture.read_text(encoding="utf-8").splitlines()
    return [json.loads(line)["entry"] for line in lines]


def demo_entries(session: Path = SESSION, engineering: Path = ENGINEERING) -> list[dict[str, Any]]:
    others = _entries(engineering)
    extra = [entry for entry in others if entry["event"] in ENGINEERING_EVENTS]
    collected = [entry for entry in others if entry["event"] == COLLECTED]
    played = _still_mining([e for e in _entries(session) if e["event"] not in DROPPED])
    refined = [i for i, entry in enumerate(played) if entry["event"] == "MiningRefined"]
    # The collected materials, spread over the mining
    collect_after = {
        refined[i * len(refined) // len(collected)]: c for i, c in enumerate(collected)
    }
    entries: list[dict[str, Any]] = []
    for index, entry in enumerate(played):
        event, at = entry["event"], entry["timestamp"]
        if event == "LoadGame":
            entries.append({"timestamp": at, "event": "Commander", "FID": "F0", "Name": COMMANDER})
        entries.append(_named(entry) if event == "LoadGame" else entry)
        if event == "Location":
            # The game writes them once loaded: the engineering view's materials and engineers
            entries.extend({**other, "timestamp": at} for other in extra)
        if index in collect_after:
            entries.append({**collect_after[index], "timestamp": at})
    return entries


def _named(load_game: dict[str, Any]) -> dict[str, Any]:
    return {**load_game, "Commander": COMMANDER, "FID": "F0", **SHIP, "GameMode": "Open"}


def _still_mining(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The entries until the commander leaves the ring after the last refined commodity."""
    last = max(i for i, entry in enumerate(entries) if entry["event"] == "MiningRefined")
    leaving = next(
        (i for i in range(last, len(entries)) if entries[i]["event"] == "SupercruiseEntry"),
        len(entries),
    )
    return entries[:leaving]


def write(path: Path = DEMO_JOURNAL) -> Path:
    lines = (json.dumps(entry, ensure_ascii=False) + "\n" for entry in demo_entries())
    path.write_text("".join(lines), encoding="utf-8", newline="\n")
    return path


def main(arguments: list[str]) -> int:
    if len(arguments) > 1:
        print(__doc__, file=sys.stderr)
        return 2
    print(write(Path(arguments[0]) if arguments else DEMO_JOURNAL))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
