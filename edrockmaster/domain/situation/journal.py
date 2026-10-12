"""Translation of raw journal entries into facts of the commander's situation (ADR 0023).

The situation context's anti-corruption layer for the game journal, built on the
tolerant helpers of the shared kernel (``journal_reading``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from edrockmaster.domain.journal_reading import (
    Entry,
    MalformedEntryError,
    Parser,
    number,
    optional,
    required,
    translate,
)


class GameMode(Enum):
    OPEN = "open"
    SOLO = "solo"
    GROUP = "group"


@dataclass(frozen=True, slots=True)
class Ship:
    symbol: str
    """As the journal writes it (``PantherMkII``, ``mamba``)."""
    type_name: str | None = None
    """In the game's language, when the journal gives it."""
    name: str | None = None
    """The name the player gave it."""
    ident: str | None = None
    """The registration the player gave it."""


@dataclass(frozen=True, slots=True)
class CommanderNamed:
    at: datetime
    name: str


@dataclass(frozen=True, slots=True)
class GameLoaded:
    at: datetime
    commander: str | None
    ship: Ship | None
    mode: GameMode | None
    group: str | None
    on_foot: bool = False
    """Loaded on foot: the journal then names the suit worn in place of a ship."""


@dataclass(frozen=True, slots=True)
class Located:
    """Where the commander is when the game starts or after a respawn (``Location``)."""

    at: datetime
    system: str
    station: str | None


@dataclass(frozen=True, slots=True)
class SystemReached:
    at: datetime
    system: str
    arrival: bool = False
    """Arrived by a jump (``FSDJump``, ``CarrierJump``), not by entering or leaving supercruise."""
    fuel_level: float | None = None
    """Tons in the main tank after a hyperspace jump."""
    fuel_used: float | None = None


@dataclass(frozen=True, slots=True)
class DockedAt:
    at: datetime
    station: str
    system: str | None


@dataclass(frozen=True, slots=True)
class Undocked:
    at: datetime


@dataclass(frozen=True, slots=True)
class ShipChanged:
    at: datetime
    ship: Ship


@dataclass(frozen=True, slots=True)
class ShipRenamed:
    at: datetime
    name: str | None
    ident: str | None


@dataclass(frozen=True, slots=True)
class OnFoot:
    at: datetime
    on_foot: bool


@dataclass(frozen=True, slots=True)
class WingJoined:
    at: datetime
    others: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WingAdded:
    at: datetime
    name: str


@dataclass(frozen=True, slots=True)
class WingLeft:
    at: datetime


@dataclass(frozen=True, slots=True)
class GameClosed:
    at: datetime


@dataclass(frozen=True, slots=True)
class RouteStop:
    system: str
    star_class: str
    """As the journal writes it (``K``, ``DA``, ``M_RedGiant``, ``TTS``)."""


@dataclass(frozen=True, slots=True)
class RoutePlotted:
    """A route plotted on the galaxy map (ADR 0043)."""

    at: datetime
    stops: tuple[RouteStop, ...]
    """From the commander's system to the destination; empty when ``NavRoute.json`` did not
    describe this very route (a line read again at start, a newer route since)."""


@dataclass(frozen=True, slots=True)
class RouteCleared:
    at: datetime


@dataclass(frozen=True, slots=True)
class JumpTargeted:
    """The next hyperspace jump (``FSDTarget``)."""

    at: datetime
    stop: RouteStop
    jumps_left: int | None
    """Jumps left in the route, this one included; ``None`` without a route."""


@dataclass(frozen=True, slots=True)
class JumpStarted:
    """A hyperspace jump begins (``StartJump``): where to, and its star."""

    at: datetime
    stop: RouteStop


@dataclass(frozen=True, slots=True)
class FuelScooped:
    at: datetime
    fuel_level: float
    """Tons in the main tank after scooping."""


type Fact = (
    CommanderNamed
    | GameLoaded
    | Located
    | SystemReached
    | DockedAt
    | Undocked
    | ShipChanged
    | ShipRenamed
    | OnFoot
    | WingJoined
    | WingAdded
    | WingLeft
    | GameClosed
    | RoutePlotted
    | RouteCleared
    | JumpTargeted
    | JumpStarted
    | FuelScooped
)

_MODES = {"open": GameMode.OPEN, "solo": GameMode.SOLO, "group": GameMode.GROUP}


def parse_entry(entry: Entry) -> Fact | None:
    """Translate one journal entry; ``None`` if irrelevant to the situation or malformed."""
    return translate(entry, _PARSERS)


def _text(entry: Entry, name: str) -> str | None:
    """A text field, ``None`` when absent or empty (the game writes ``""`` for no name)."""
    value = optional(entry, name, str)
    return value.strip() or None if value is not None else None


def _commander(entry: Entry, at: datetime) -> CommanderNamed:
    name = _text(entry, "Name")
    if name is None:
        raise MalformedEntryError("Name")
    return CommanderNamed(at, name)


def _loaded(entry: Entry, at: datetime) -> GameLoaded:
    symbol = _text(entry, "Ship")
    # On foot, LoadGame names the suit (``UtilitySuit_Class2``) where a ship would be
    on_foot = symbol is not None and "suit" in symbol.lower()
    if on_foot:
        symbol = None
    ship = (
        Ship(
            symbol,
            _text(entry, "Ship_Localised"),
            _text(entry, "ShipName"),
            _text(entry, "ShipIdent"),
        )
        if symbol
        else None
    )
    mode = _MODES.get((_text(entry, "GameMode") or "").lower())
    group = _text(entry, "Group") if mode is GameMode.GROUP else None
    return GameLoaded(at, _text(entry, "Commander"), ship, mode, group, on_foot)


def _located(entry: Entry, at: datetime) -> Located:
    docked = optional(entry, "Docked", bool) or False
    station = (
        (_text(entry, "StationName_Localised") or _text(entry, "StationName")) if docked else None
    )
    return Located(at, required(entry, "StarSystem", str), station)


def _reached(entry: Entry, at: datetime) -> SystemReached:
    return SystemReached(at, required(entry, "StarSystem", str))


def _jumped(entry: Entry, at: datetime) -> SystemReached:
    return SystemReached(
        at,
        required(entry, "StarSystem", str),
        arrival=True,
        fuel_level=number(entry, "FuelLevel"),
        fuel_used=number(entry, "FuelUsed"),
    )


def _docked(entry: Entry, at: datetime) -> DockedAt:
    station = _text(entry, "StationName_Localised") or _text(entry, "StationName")
    if station is None:
        raise MalformedEntryError("StationName")
    return DockedAt(at, station, _text(entry, "StarSystem"))


def _undocked(_entry: Entry, at: datetime) -> Undocked:
    return Undocked(at)


def _loadout(entry: Entry, at: datetime) -> ShipChanged:
    return ShipChanged(
        at,
        Ship(
            required(entry, "Ship", str), None, _text(entry, "ShipName"), _text(entry, "ShipIdent")
        ),
    )


def _swapped(entry: Entry, at: datetime) -> ShipChanged:
    return ShipChanged(
        at, Ship(required(entry, "ShipType", str), _text(entry, "ShipType_Localised"))
    )


def _renamed(entry: Entry, at: datetime) -> ShipRenamed:
    return ShipRenamed(at, _text(entry, "UserShipName"), _text(entry, "UserShipId"))


def _disembarked(_entry: Entry, at: datetime) -> OnFoot:
    return OnFoot(at, on_foot=True)


def _embarked(_entry: Entry, at: datetime) -> OnFoot:
    return OnFoot(at, on_foot=False)


def _joined(entry: Entry, at: datetime) -> WingJoined:
    others = optional(entry, "Others", list) or []
    names = []
    for other in others:
        # Older journals list names; newer ones may list objects with a Name
        name = other.get("Name") if isinstance(other, dict) else other
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return WingJoined(at, tuple(names))


def _added(entry: Entry, at: datetime) -> WingAdded:
    name = _text(entry, "Name")
    if name is None:
        raise MalformedEntryError("Name")
    return WingAdded(at, name)


def _left(_entry: Entry, at: datetime) -> WingLeft:
    return WingLeft(at)


def _closed(_entry: Entry, at: datetime) -> GameClosed:
    return GameClosed(at)


def _plotted(entry: Entry, at: datetime) -> RoutePlotted:
    """The list is added from ``NavRoute.json`` by the journal reader, when it describes this
    very line; a stop the game wrote oddly makes the whole list unknown."""
    route = entry.get("Route")
    if not isinstance(route, list):
        return RoutePlotted(at, ())
    try:
        stops = tuple(_stop(stop, "StarSystem") for stop in route if isinstance(stop, dict))
    except MalformedEntryError:
        return RoutePlotted(at, ())
    return RoutePlotted(at, stops if len(stops) == len(route) else ())


def _stop(entry: Entry, name: str) -> RouteStop:
    return RouteStop(required(entry, name, str), required(entry, "StarClass", str))


def _cleared(_entry: Entry, at: datetime) -> RouteCleared:
    return RouteCleared(at)


def _targeted(entry: Entry, at: datetime) -> JumpTargeted:
    return JumpTargeted(at, _stop(entry, "Name"), optional(entry, "RemainingJumpsInRoute", int))


def _started(entry: Entry, at: datetime) -> JumpStarted | None:
    if entry.get("JumpType") != "Hyperspace":
        return None
    return JumpStarted(at, _stop(entry, "StarSystem"))


def _scooped(entry: Entry, at: datetime) -> FuelScooped:
    total = number(entry, "Total")
    if total is None:
        raise MalformedEntryError("Total")
    return FuelScooped(at, total)


_PARSERS: dict[str, Parser[Fact | None]] = {
    "Commander": _commander,
    "LoadGame": _loaded,
    "Location": _located,
    "FSDJump": _jumped,
    "CarrierJump": _jumped,
    "SupercruiseEntry": _reached,
    "SupercruiseExit": _reached,
    "Docked": _docked,
    "Undocked": _undocked,
    "Loadout": _loadout,
    "ShipyardSwap": _swapped,
    "SetUserShipName": _renamed,
    "Disembark": _disembarked,
    "Embark": _embarked,
    "WingJoin": _joined,
    "WingAdd": _added,
    "WingLeave": _left,
    "Shutdown": _closed,
    "NavRoute": _plotted,
    "NavRouteClear": _cleared,
    "FSDTarget": _targeted,
    "StartJump": _started,
    "FuelScoop": _scooped,
}
