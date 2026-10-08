"""Import the game data of ship engineering into the plugin (ADR 0017).

Reads EDCD/FDevIDs (materials, engineers) and EDCD/coriolis-data (blueprints,
experimental effects, which engineer offers which grade on which module) at
the pinned commits below, keeps the fields the plugin uses, maps every
ingredient to its journal symbol, and writes
``edrockmaster/domain/engineering/catalogue.json``.

The data is Frontier Developments' intellectual property (see ``NOTICE``), used
as community tools use it; it is not under the plugin's licence.

To follow a game update: change the pinned commits and dates, run the script,
review the diff of the catalogue, and open a pull request. The script refuses a
name it cannot map rather than guess: fix the source upstream, or add a mapping
below with its reason.

Usage: python3 scripts/import_engineering_data.py [<catalogue.json>]
"""

from __future__ import annotations

import csv
import io
import json
import sys
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FORMAT = 1


@dataclass(frozen=True, slots=True)
class Source:
    repository: str
    commit: str
    date: str
    """Date of the commit, shown by the plugin as the date of its data."""


FDEVIDS = Source("EDCD/FDevIDs", "c35612952dd6a547d1a7ac4cffab9c7051e86579", "2026-09-05")
CORIOLIS = Source("EDCD/coriolis-data", "0db9234b5b9ce8c939ea84133d7ce336eea88e27", "2026-04-24")

CATEGORIES = {"Raw": "raw", "Manufactured": "manufactured", "Encoded": "encoded"}

INGREDIENT_FIXES = {
    # Misspelt in coriolis-data (FDevIDs and the game: "Encryptors")
    "Adaptive Encyptors Capture": "Adaptive Encryptors Capture",
}
ENGINEER_FIXES = {
    # Misspelt in coriolis-data
    "Felicty Farseer": "Felicity Farseer",
    # coriolis-data quotes the nickname with double quotes, FDevIDs and the game with single ones
    'Tod "The Blaster" McQuinn': "Tod 'The Blaster' McQuinn",
}

MODULE_NAMES = {
    # coriolis-data names its module groups by code only: the names the game uses
    "advmc": "Advanced multi-cannon",
    "am": "Auto field-maintenance unit",
    "amr": "Advanced missile rack",
    "bh": "Armour",
    "bl": "Beam laser",
    "bsg": "Bi-weave shield generator",
    "c": "Cannon",
    "cc": "Collector limpet controller",
    "ch": "Chaff launcher",
    "cr": "Cargo rack",
    "cs": "Manifest scanner",
    "csl": "Caustic sink launcher",
    "ec": "Electronic countermeasure",
    "fc": "Fragment cannon",
    "fi": "Frame shift drive interdictor",
    "fs": "Fuel scoop",
    "fsd": "Frame shift drive",
    "fx": "Fuel transfer limpet controller",
    "hb": "Hatch breaker limpet controller",
    "hr": "Hull reinforcement package",
    "hs": "Heat sink launcher",
    "kw": "Kill warrant scanner",
    "ls": "Life support",
    "mc": "Multi-cannon",
    "mr": "Missile rack",
    "nl": "Mine launcher",
    "pa": "Plasma accelerator",
    "pc": "Prospector limpet controller",
    "pd": "Power distributor",
    "pl": "Pulse laser",
    "po": "Point defence",
    "pp": "Power plant",
    "psg": "Prismatic shield generator",
    "rf": "Refinery",
    "rg": "Rail gun",
    "s": "Sensors",
    "sb": "Shield booster",
    "scb": "Shield cell bank",
    "sg": "Shield generator",
    "ss": "Detailed surface scanner",
    "t": "Thrusters",
    "tp": "Torpedo pylon",
    "ul": "Burst laser",
    "ws": "Frame shift wake scanner",
}

# A module lists its experimental effects in "specials"; missile racks have one list per
# variant (D: dumbfire, S: seeker), merged here
EFFECT_LISTS = ("specials", "specials_D", "specials_S")

type Read = Callable[[Source, str], str]
"""Returns the text of a file of a source, at its pinned commit."""


class ImportRefused(Exception):  # noqa: N818 - a refusal, not a programming error
    """The sources hold a name the script cannot map: nothing is written."""


def read_github(source: Source, path: str) -> str:
    url = f"https://raw.githubusercontent.com/{source.repository}/{source.commit}/{path}"
    with urllib.request.urlopen(url, timeout=30) as response:
        text: str = response.read().decode("utf-8")
    return text


def _materials(read: Read) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Materials by journal symbol, and the symbol of each English name."""
    materials: dict[str, dict[str, Any]] = {}
    symbols: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(read(FDEVIDS, "material.csv"))):
        symbol = row["symbol"].strip().lower()  # the journal writes symbols in lower case
        name = row["name"].strip()  # FDevIDs has trailing spaces ("Untypical Shield Scans ")
        materials[symbol] = {
            "category": CATEGORIES[row["type"].strip()],
            "grade": int(row["rarity"]),
            "name": name,
        }
        symbols[name] = symbol
    return materials, symbols


def _engineers(read: Read) -> dict[str, int]:
    """Engineer id by name."""
    rows = csv.DictReader(io.StringIO(read(FDEVIDS, "engineers.csv")))
    return {row["name"].strip(): int(row["id"]) for row in rows}


def _ingredients(components: Mapping[str, int], symbols: Mapping[str, str]) -> dict[str, int]:
    ingredients = {}
    for name, count in components.items():
        fixed = INGREDIENT_FIXES.get(name, name)
        if fixed not in symbols:
            raise ImportRefused(f"ingredient {name!r} is no material of FDevIDs")
        ingredients[symbols[fixed]] = count
    return dict(sorted(ingredients.items()))


def _engineer_ids(names: list[str], engineers: Mapping[str, int]) -> list[int]:
    ids = []
    for name in names:
        fixed = ENGINEER_FIXES.get(name, name)
        if fixed not in engineers:
            raise ImportRefused(f"engineer {name!r} is not in FDevIDs")
        ids.append(engineers[fixed])
    return sorted(ids)


def build_catalogue(read: Read) -> dict[str, Any]:
    materials, symbols = _materials(read)
    engineer_ids = _engineers(read)
    blueprints_data = json.loads(read(CORIOLIS, "modifications/blueprints.json"))
    modules_data = json.loads(read(CORIOLIS, "modifications/modules.json"))
    effects_data = json.loads(read(CORIOLIS, "modifications/specials.json"))

    modules: dict[str, Any] = {}
    used_blueprints: set[str] = set()
    used_effects: set[str] = set()
    used_engineers: set[int] = set()
    for key, module in sorted(modules_data.items()):
        if not module["blueprints"]:
            continue  # not engineerable
        if key not in MODULE_NAMES:
            raise ImportRefused(f"module {key!r} has no name in MODULE_NAMES")
        offers: dict[str, dict[str, list[int]]] = {}
        for blueprint, offer in sorted(module["blueprints"].items()):
            if blueprint not in blueprints_data:
                raise ImportRefused(f"module {key!r} offers an unknown blueprint {blueprint!r}")
            grades = {
                grade: _engineer_ids(details.get("engineers", []), engineer_ids)
                for grade, details in sorted(offer["grades"].items())
            }
            offers[blueprint] = grades
            used_blueprints.add(blueprint)
            used_engineers.update(id_ for ids in grades.values() for id_ in ids)
        listed = {effect for field in EFFECT_LISTS for effect in module.get(field, [])}
        for effect in listed:
            if effect not in effects_data:
                raise ImportRefused(f"module {key!r} offers an unknown effect {effect!r}")
        # Effects without ingredients are legacy ones, on old modules only: no engineer applies them
        craftable = sorted(effect for effect in listed if "components" in effects_data[effect])
        used_effects.update(craftable)
        modules[key] = {"name": MODULE_NAMES[key], "blueprints": offers, "effects": craftable}

    blueprints = {
        name: {
            "name": blueprints_data[name]["name"],
            "grades": {
                grade: _ingredients(details["components"], symbols)
                for grade, details in sorted(blueprints_data[name]["grades"].items())
            },
        }
        for name in sorted(used_blueprints)
    }
    effects = {
        name: {
            "name": effects_data[name]["name"],
            "ingredients": _ingredients(effects_data[name]["components"], symbols),
        }
        for name in sorted(used_effects)
    }
    engineers = {
        str(id_): name for name, id_ in sorted(engineer_ids.items()) if id_ in used_engineers
    }
    return {
        "format": FORMAT,
        "sources": [
            {"repository": source.repository, "commit": source.commit, "date": source.date}
            for source in (FDEVIDS, CORIOLIS)
        ],
        "materials": dict(sorted(materials.items())),
        "engineers": dict(sorted(engineers.items(), key=lambda item: int(item[0]))),
        "blueprints": blueprints,
        "effects": effects,
        "modules": modules,
    }


def render(catalogue: Mapping[str, Any]) -> str:
    """The catalogue as written: stable, one entry per line, for readable diffs."""
    lines = ["{"]
    sections = list(catalogue.items())
    for index, (section, value) in enumerate(sections):
        comma = "," if index < len(sections) - 1 else ""
        if isinstance(value, dict):
            lines.append(f"  {json.dumps(section)}: {{")
            entries = list(value.items())
            for entry_index, (key, entry) in enumerate(entries):
                entry_comma = "," if entry_index < len(entries) - 1 else ""
                text = json.dumps(entry, ensure_ascii=False)
                lines.append(f"    {json.dumps(key)}: {text}{entry_comma}")
            lines.append(f"  }}{comma}")
        else:
            lines.append(f"  {json.dumps(section)}: {json.dumps(value)}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent / "edrockmaster/domain/engineering/catalogue.json"
)


def main(argv: list[str], read: Read = read_github) -> int:
    if len(argv) > 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    output = Path(argv[1]) if len(argv) == 2 else DEFAULT_OUTPUT
    try:
        catalogue = build_catalogue(read)
    except ImportRefused as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 1
    output.write_text(render(catalogue), encoding="utf-8", newline="\n")
    print(
        f"{output}: {len(catalogue['materials'])} materials, "
        f"{len(catalogue['blueprints'])} blueprints, {len(catalogue['effects'])} effects, "
        f"{len(catalogue['modules'])} modules, {len(catalogue['engineers'])} engineers"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
