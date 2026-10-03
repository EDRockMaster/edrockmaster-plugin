"""Translation of raw journal entries into facts of the mining domain.

This module is the plugin's anti-corruption layer for the game journal: the
rest of the domain never sees a raw entry. It is a tolerant reader: unknown
events, unknown fields and malformed entries are ignored, never fatal.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from edrockmaster.domain.commodities import LIMPET, Commodity

type Entry = Mapping[str, object]


class ContentLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class LimpetKind(Enum):
    PROSPECTOR = "prospector"
    COLLECTOR = "collector"
    OTHER = "other"


class LeaveReason(Enum):
    SUPERCRUISE = "supercruise"
    JUMP = "jump"
    DOCKED = "docked"
    GAME_CLOSED = "game_closed"


@dataclass(frozen=True, slots=True)
class MaterialShare:
    commodity: Commodity
    proportion: float


@dataclass(frozen=True, slots=True)
class AsteroidProspected:
    at: datetime
    materials: tuple[MaterialShare, ...]
    content: ContentLevel
    remaining: float | None
    motherlode: Commodity | None


@dataclass(frozen=True, slots=True)
class CommodityRefined:
    at: datetime
    commodity: Commodity


@dataclass(frozen=True, slots=True)
class LimpetLaunched:
    at: datetime
    kind: LimpetKind


@dataclass(frozen=True, slots=True)
class AsteroidCracked:
    at: datetime


@dataclass(frozen=True, slots=True)
class RingEntered:
    at: datetime
    system: str
    system_address: int | None
    ring: str


@dataclass(frozen=True, slots=True)
class MiningAreaLeft:
    at: datetime
    reason: LeaveReason


@dataclass(frozen=True, slots=True)
class CargoChanged:
    at: datetime
    total: int
    inventory: tuple[tuple[Commodity, int], ...]

    def tons_of(self, commodity: Commodity) -> int:
        return sum(count for item, count in self.inventory if item == commodity)

    @property
    def limpets(self) -> int:
        return self.tons_of(LIMPET)


@dataclass(frozen=True, slots=True)
class CargoEjected:
    at: datetime
    commodity: Commodity
    count: int


@dataclass(frozen=True, slots=True)
class CommoditySold:
    at: datetime
    commodity: Commodity
    count: int
    unit_price: int
    total: int


@dataclass(frozen=True, slots=True)
class GameLoaded:
    at: datetime
    game_version: str
    is_live: bool


type Fact = (
    AsteroidProspected
    | CommodityRefined
    | LimpetLaunched
    | AsteroidCracked
    | RingEntered
    | MiningAreaLeft
    | CargoChanged
    | CargoEjected
    | CommoditySold
    | GameLoaded
)


class _MalformedEntryError(Exception):
    """Raised internally when an entry lacks a required field or has a wrong type."""


def parse_entry(entry: Entry) -> Fact | None:
    """Return the domain fact carried by a journal entry, or ``None`` if irrelevant."""
    event = entry.get("event")
    parser = _PARSERS.get(event) if isinstance(event, str) else None
    if parser is None:
        return None
    try:
        return parser(entry, _timestamp(entry))
    except _MalformedEntryError:
        return None


# --- field access -------------------------------------------------------------------------


def _timestamp(entry: Entry) -> datetime:
    raw = _required(entry, "timestamp", str)
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise _MalformedEntryError from error


def _required[T](entry: Entry, name: str, kind: type[T]) -> T:
    value = entry.get(name)
    if not isinstance(value, kind) or (isinstance(value, bool) and kind is not bool):
        raise _MalformedEntryError(name)
    return value


def _optional[T](entry: Entry, name: str, kind: type[T]) -> T | None:
    return _required(entry, name, kind) if name in entry else None


def _number(entry: Entry, name: str) -> float | None:
    value = entry.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _MalformedEntryError(name)
    return float(value)


def _commodity(entry: Entry, name: str) -> Commodity:
    try:
        return Commodity.from_symbol(
            _required(entry, name, str), _optional(entry, f"{name}_Localised", str)
        )
    except ValueError as error:
        raise _MalformedEntryError(name) from error


def _items(entry: Entry, name: str) -> list[Entry]:
    items = _required(entry, name, list)
    if not all(isinstance(item, Mapping) for item in items):
        raise _MalformedEntryError(name)
    return items


# --- parsers ------------------------------------------------------------------------------

_CONTENT_LEVELS = {
    "$asteroidmaterialcontent_high;": ContentLevel.HIGH,
    "$asteroidmaterialcontent_medium;": ContentLevel.MEDIUM,
    "$asteroidmaterialcontent_low;": ContentLevel.LOW,
}

_LIMPET_KINDS = {"prospector": LimpetKind.PROSPECTOR, "collection": LimpetKind.COLLECTOR}

_LEAVE_REASONS = {
    "SupercruiseEntry": LeaveReason.SUPERCRUISE,
    "FSDJump": LeaveReason.JUMP,
    "Docked": LeaveReason.DOCKED,
    "Shutdown": LeaveReason.GAME_CLOSED,
    "ShutDown": LeaveReason.GAME_CLOSED,  # synthetic event from EDMC when the game crashed
}


def _prospected(entry: Entry, at: datetime) -> AsteroidProspected:
    materials = tuple(
        MaterialShare(_commodity(item, "Name"), _number(item, "Proportion") or 0.0)
        for item in _items(entry, "Materials")
    )
    content = _optional(entry, "Content", str) or ""
    motherlode = _commodity(entry, "MotherlodeMaterial") if "MotherlodeMaterial" in entry else None
    return AsteroidProspected(
        at=at,
        materials=materials,
        content=_CONTENT_LEVELS.get(content.lower(), ContentLevel.UNKNOWN),
        remaining=_number(entry, "Remaining"),
        motherlode=motherlode,
    )


def _refined(entry: Entry, at: datetime) -> CommodityRefined:
    return CommodityRefined(at=at, commodity=_commodity(entry, "Type"))


def _limpet(entry: Entry, at: datetime) -> LimpetLaunched:
    kind = _required(entry, "Type", str).lower()
    return LimpetLaunched(at=at, kind=_LIMPET_KINDS.get(kind, LimpetKind.OTHER))


def _cracked(_entry: Entry, at: datetime) -> AsteroidCracked:
    return AsteroidCracked(at=at)


def _ring_position(entry: Entry, at: datetime) -> RingEntered | None:
    """Dropping out of supercruise in a ring, or the game (or EDMC) starting inside one."""
    if entry.get("BodyType") != "PlanetaryRing":
        return None
    return RingEntered(
        at=at,
        system=_required(entry, "StarSystem", str),
        system_address=_optional(entry, "SystemAddress", int),
        ring=_required(entry, "Body", str),
    )


def _left(entry: Entry, at: datetime) -> MiningAreaLeft:
    return MiningAreaLeft(at=at, reason=_LEAVE_REASONS[_required(entry, "event", str)])


def _cargo(entry: Entry, at: datetime) -> CargoChanged | None:
    if entry.get("Vessel") != "Ship" or "Inventory" not in entry:
        return None
    inventory = tuple(
        (_commodity(item, "Name"), _required(item, "Count", int))
        for item in _items(entry, "Inventory")
    )
    return CargoChanged(at=at, total=_required(entry, "Count", int), inventory=inventory)


def _ejected(entry: Entry, at: datetime) -> CargoEjected:
    return CargoEjected(
        at=at, commodity=_commodity(entry, "Type"), count=_required(entry, "Count", int)
    )


def _sold(entry: Entry, at: datetime) -> CommoditySold:
    count = _required(entry, "Count", int)
    if count <= 0:
        raise _MalformedEntryError("Count")
    return CommoditySold(
        at=at,
        commodity=_commodity(entry, "Type"),
        count=count,
        unit_price=_required(entry, "SellPrice", int),
        total=_required(entry, "TotalSale", int),
    )


def _game_loaded(entry: Entry, at: datetime) -> GameLoaded:
    version = _required(entry, "gameversion", str)
    return GameLoaded(at=at, game_version=version, is_live=version.startswith("4."))


_PARSERS: dict[str, Callable[[Entry, datetime], Fact | None]] = {
    "ProspectedAsteroid": _prospected,
    "MiningRefined": _refined,
    "LaunchDrone": _limpet,
    "AsteroidCracked": _cracked,
    "SupercruiseExit": _ring_position,
    "Location": _ring_position,
    "StartUp": _ring_position,  # synthetic event from EDMC when started with the game running
    "Cargo": _cargo,
    "EjectCargo": _ejected,
    "MarketSell": _sold,
    "LoadGame": _game_loaded,
    **dict.fromkeys(_LEAVE_REASONS, _left),
}
