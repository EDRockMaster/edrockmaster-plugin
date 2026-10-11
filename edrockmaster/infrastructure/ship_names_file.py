"""Reads the ship type names shipped with the application (ADR 0023): FDevIDs' English names,
by lower-case symbol, shown until the journal gives the game's own."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from edrockmaster.domain.situation import situation as situation_module

SHIP_NAMES_FILE = Path(situation_module.__file__).with_name("ship_names.json")


def load_ship_names(path: Path = SHIP_NAMES_FILE) -> Mapping[str, str]:
    names = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(names, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in names.items()
    ):
        raise ValueError(f"{path} is not a table of ship names")
    return names
