"""Import the names of the ship types into the application (ADR 0023).

The journal names a ship type in the game's language only in ``LoadGame`` and
``ShipyardSwap``; ``Loadout`` gives its symbol alone (``panthermkii``). Until
the journal gives the game's own name, the situation shows FDevIDs' English
name. Reads EDCD/FDevIDs' ``shipyard.csv`` at the commit the engineering
catalogue pins, and writes ``edrockmaster/domain/situation/ship_names.json``:
English name by lower-case symbol.

The data is Frontier Developments' intellectual property (see ``NOTICE``).

Usage: python3 scripts/import_ship_names.py [<ship_names.json>]
"""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "edrockmaster/domain/situation/ship_names.json"

type Read = Callable[[Any, str], str]


def _engineering_import() -> Any:
    """The engineering import, for its pinned FDevIDs commit and its reader."""
    spec = importlib.util.spec_from_file_location(
        "import_engineering_data", Path(__file__).with_name("import_engineering_data.py")
    )
    if spec is None or spec.loader is None:  # pragma: no cover - the file is beside this one
        raise ImportRefused("scripts/import_engineering_data.py is missing")
    module = importlib.util.module_from_spec(spec)
    # Its dataclasses look their module up while they are made
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


class ImportRefused(Exception):  # noqa: N818 - a refusal, not a programming error
    """The source holds what the script cannot take: nothing is written."""


def ship_names(text: str) -> dict[str, str]:
    """English name by lower-case symbol."""
    names: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(text)):
        symbol, name = row["symbol"].strip().lower(), row["name"].strip()
        if not symbol or not name:
            raise ImportRefused(f"a ship without its symbol or name: {row!r}")
        names[symbol] = name
    return dict(sorted(names.items()))


def main(argv: list[str], read: Read | None = None) -> int:
    if len(argv) > 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    engineering = _engineering_import()
    output = Path(argv[1]) if len(argv) == 2 else DEFAULT_OUTPUT
    try:
        names = ship_names((read or engineering.read_github)(engineering.FDEVIDS, "shipyard.csv"))
    except ImportRefused as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 1
    lines = ",\n".join(f"  {json.dumps(k)}: {json.dumps(v)}" for k, v in names.items())
    output.write_text("{\n" + lines + "\n}\n", encoding="utf-8", newline="\n")
    print(f"{output}: {len(names)} ship types")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
