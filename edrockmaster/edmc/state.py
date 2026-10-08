"""What EDMC's ``state`` tells the engineering context when the plugin starts after the game.

EDMC reads the current journal when it starts and keeps the inventory
(``state['Raw']``, ``['Manufactured']``, ``['Encoded']``: symbol in lower case →
count) and the engineers (``state['Engineers']``: name → ``(rank, progress)``
once unlocked, else the status as text). Plugins are not handed the events it
read before they started: this is how the plugin learns them (ADR 0017).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from edrockmaster.domain.engineering.catalogue import Catalogue
from edrockmaster.domain.engineering.journal import (
    EngineersStated,
    EngineerState,
    EngineerStatus,
    InventoryStated,
    MaterialChange,
)

_CATEGORIES = ("Raw", "Manufactured", "Encoded")


def inventory_from_state(state: Mapping[str, object], at: datetime) -> InventoryStated | None:
    """The inventory EDMC knows; ``None`` if it knows none (an empty one means unknown)."""
    counts = []
    for category in _CATEGORIES:
        held = state.get(category)
        if not isinstance(held, Mapping):
            continue
        counts += [
            MaterialChange(symbol.lower(), count)
            for symbol, count in held.items()
            if isinstance(symbol, str) and isinstance(count, int) and count > 0
        ]
    return InventoryStated(at, tuple(counts)) if counts else None


def engineers_from_state(
    state: Mapping[str, object], catalogue: Catalogue, at: datetime
) -> EngineersStated | None:
    """The engineers EDMC knows, those of the catalogue only (it names them, without ids)."""
    known = state.get("Engineers")
    if not isinstance(known, Mapping) or not known:
        return None
    ids = {name: id_ for id_, name in catalogue.engineers.items()}
    engineers = []
    for name, progress in known.items():
        if name not in ids:
            continue
        if isinstance(progress, tuple) and progress and isinstance(progress[0], int):
            engineers.append(EngineerState(ids[name], name, EngineerStatus.UNLOCKED, progress[0]))
        elif isinstance(progress, str):
            try:
                engineers.append(EngineerState(ids[name], name, EngineerStatus(progress)))
            except ValueError:
                continue
    return EngineersStated(at, tuple(engineers)) if engineers else None
