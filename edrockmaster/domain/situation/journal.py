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
    return GameLoaded(at, _text(entry, "Commander"), ship, mode, group)


def _located(entry: Entry, at: datetime) -> Located:
    docked = optional(entry, "Docked", bool) or False
    station = (
        (_text(entry, "StationName_Localised") or _text(entry, "StationName")) if docked else None
    )
    return Located(at, required(entry, "StarSystem", str), station)


def _reached(entry: Entry, at: datetime) -> SystemReached:
    return SystemReached(at, required(entry, "StarSystem", str))


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


_PARSERS: dict[str, Parser[Fact]] = {
    "Commander": _commander,
    "LoadGame": _loaded,
    "Location": _located,
    "FSDJump": _reached,
    "CarrierJump": _reached,
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
}
