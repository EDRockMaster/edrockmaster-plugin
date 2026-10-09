"""The demo mode of the desktop application: a sample journal instead of the player's.

``--demo`` shows the application at work, for screenshots (Microsoft Store,
documentation) or to discover it without playing: it reads a journal shipped
with it (``demo_journal.jsonl``, written by ``scripts/make_demo_journal.py``),
whose timestamps are moved so that it ends now, as if the session was still
running. Its settings and goals live in a temporary folder, deleted at exit:
the player's own are neither read nor changed.

The journal was recorded with the game in French. The names the game writes in
its language and the application shows as they are (commodities, asteroid
content, community goal) are given in English for a demo in English, as the
game in English would write them: the screenshots in each language are then
in that language only. Materials are named by the application's catalogue.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

DEMO_JOURNAL = Path(__file__).with_name("demo_journal.jsonl")
_GAME_TIME = "%Y-%m-%dT%H:%M:%SZ"
"""How the game writes the journal's timestamps (UTC)."""
RECORDED_IN = "fr"
ENGLISH = {
    "Tritium": "Tritium",
    "Bromellite": "Bromellite",
    "Hydrate de méthane": "Methane Clathrate",
    "Diamants basse température": "Low Temperature Diamonds",
    "Hydroxyde de lithium": "Lithium Hydroxide",
    "Eau": "Water",
    "Cristaux de méthanol monohydraté": "Methanol Monohydrate Crystals",
    "Peroxyde d'hydrogène": "Hydrogen Peroxide",
    "Oxygène liquide": "Liquid oxygen",
    "Drone": "Limpet",
    "Zone de conflit [forte intensité]": "Conflict Zone [High Intensity]",
    "Présence de matériaux\u00a0: faible": "Material Content: Low",
    "Présence de matériaux\u00a0: moyenne": "Material Content: Medium",
    "Éliminez les pilotes criminels dans le système Redonesses": (
        "Eliminate criminal pilots in the Redonesses system"
    ),
}
"""The game's names in French that the application shows, and the game's in English."""
SHOWN_NAMES = (
    "Type_Localised",
    "Name_Localised",
    "Content_Localised",
    "MotherlodeMaterial_Localised",
    "Title",
)


def write_demo_journal(
    folder: Path, now: datetime, language: str = RECORDED_IN, source: Path = DEMO_JOURNAL
) -> Path:
    """Write the demo journal in ``folder`` as the game would, ending at ``now`` (UTC), with
    the names of the game in ``language`` (``fr``, else English)."""
    entries = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
    if language != RECORDED_IN:
        entries = [_in_english(entry) for entry in entries]
    times = [datetime.strptime(entry["timestamp"], _GAME_TIME) for entry in entries]
    shift = now.replace(tzinfo=None, microsecond=0) - times[-1]
    for entry, at in zip(entries, times, strict=True):
        entry["timestamp"] = (at + shift).strftime(_GAME_TIME)
    folder.mkdir(parents=True, exist_ok=True)
    journal = folder / f"Journal.{times[0] + shift:%Y-%m-%dT%H%M%S}.01.log"
    lines = (json.dumps(entry, ensure_ascii=False) + "\r\n" for entry in entries)
    journal.write_text("".join(lines), encoding="utf-8", newline="")
    return journal


def _in_english(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ENGLISH.get(item, item)
            if key in SHOWN_NAMES and isinstance(item, str)
            else _in_english(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_in_english(item) for item in value]
    return value
