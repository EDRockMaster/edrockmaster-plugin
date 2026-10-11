"""Hotspots: where a ring holds more of a commodity (ADR 0040).

Only some commodities have hotspots. Each source names them its own way: the
journal and Spansh's system dump by the game's symbol (``LowTemperatureDiamond``),
Spansh's search by the game's English name (``Low Temperature Diamonds``),
Ardent by the symbol in lower case. ``hotspot_commodity`` reads them all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from edrockmaster.domain.commodities import Commodity

PAGE_SIZE = 10
"""Rings shown at a time."""

DEFAULT_MAX_DISTANCE = 50.0
"""Light years around the reference system."""


@dataclass(frozen=True, slots=True)
class HotspotCommodity:
    key: str
    """The application's key of the commodity (``Commodity.key``)."""
    english: str
    """The game's English name, as its galaxy map shows it."""


HOTSPOT_COMMODITIES: tuple[HotspotCommodity, ...] = (
    HotspotCommodity("alexandrite", "Alexandrite"),
    HotspotCommodity("benitoite", "Benitoite"),
    HotspotCommodity("bromellite", "Bromellite"),
    HotspotCommodity("grandidierite", "Grandidierite"),
    HotspotCommodity("lowtemperaturediamond", "Low Temperature Diamonds"),
    HotspotCommodity("monazite", "Monazite"),
    HotspotCommodity("musgravite", "Musgravite"),
    HotspotCommodity("painite", "Painite"),
    HotspotCommodity("platinum", "Platinum"),
    HotspotCommodity("rhodplumsite", "Rhodplumsite"),
    HotspotCommodity("serendibite", "Serendibite"),
    HotspotCommodity("tritium", "Tritium"),
    HotspotCommodity("opal", "Void Opal"),
)


def _folded(name: str) -> str:
    return "".join(character for character in name.lower() if character.isalnum())


_BY_NAME: dict[str, HotspotCommodity] = {
    name: commodity
    for commodity in HOTSPOT_COMMODITIES
    for name in (commodity.key, _folded(commodity.english))
}


def hotspot_commodity(name: str) -> HotspotCommodity | None:
    """The hotspot commodity a source names, whatever its spelling; ``None`` if it has none."""
    try:
        key = Commodity.from_symbol(name).key
    except ValueError:
        return None
    return _BY_NAME.get(key) or _BY_NAME.get(_folded(name))


class ReserveLevel(Enum):
    """How much a ring still holds, from the richest."""

    PRISTINE = "pristine"
    MAJOR = "major"
    COMMON = "common"
    LOW = "low"
    DEPLETED = "depleted"

    @classmethod
    def from_name(cls, name: str | None) -> ReserveLevel | None:
        try:
            return cls(name.strip().lower()) if name else None
        except ValueError:
            return None


@dataclass(frozen=True, slots=True)
class HotspotQuery:
    """Where to mine a commodity: rings with its hotspots around a system."""

    commodity: HotspotCommodity
    reference: str
    """The system the distances are measured from, by name."""
    minimum_count: int = 1
    """Hotspots of the commodity a ring has at least."""
    reserves: frozenset[ReserveLevel] = frozenset()
    """The reserve levels accepted; empty: any."""
    max_distance: float = DEFAULT_MAX_DISTANCE
    page: int = 0
    """Which ``PAGE_SIZE`` rings, nearest first."""

    def __post_init__(self) -> None:
        reference = self.reference.strip()
        if not reference:
            raise ValueError("a reference system is needed")
        object.__setattr__(self, "reference", reference)
        if self.minimum_count < 1:
            raise ValueError("at least one hotspot")
        if self.max_distance <= 0:
            raise ValueError("the distance must be positive")
        if self.page < 0:
            raise ValueError("the first page is 0")


@dataclass(frozen=True, slots=True)
class Ring:
    """A ring with hotspots, as a source knows it."""

    system: str
    body: str
    name: str
    ring_type: str
    """As the game names it: ``Metal Rich``, ``Icy``, ``Rocky``, ``Metallic``."""
    reserve: ReserveLevel | None
    hotspots: tuple[tuple[str, int], ...]
    """Hotspot counts by commodity key."""
    distance: float
    """Light years from the reference system."""
    arrival: float | None
    """Light seconds from the system's arrival point to the body."""
    seen: datetime | None
    """When the source last saw the hotspots."""

    def count(self, commodity: HotspotCommodity) -> int:
        return dict(self.hotspots).get(commodity.key, 0)


@dataclass(frozen=True, slots=True)
class HotspotPage:
    """One page of the rings a query found, nearest first."""

    query: HotspotQuery
    rings: tuple[Ring, ...]
    total: int
    """How many rings the source found in all."""

    @property
    def has_more(self) -> bool:
        return (self.query.page + 1) * PAGE_SIZE < self.total
