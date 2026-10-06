"""Translation of raw journal entries into facts of the trade domain.

The trade context's anti-corruption layer for the game journal, built on the
tolerant helpers of the shared kernel (``journal_reading``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.journal_reading import (
    Entry,
    MalformedEntryError,
    Parser,
    commodity,
    items,
    optional,
    required,
    translate,
)


@dataclass(frozen=True, slots=True)
class Market:
    """A market, identified by the game's ``MarketID``; the names only serve for display."""

    market_id: int
    station: str | None = field(default=None, compare=False)
    system: str | None = field(default=None, compare=False)


@dataclass(frozen=True, slots=True)
class GoodsBought:
    at: datetime
    market_id: int
    commodity: Commodity
    count: int
    unit_price: int
    total: int


@dataclass(frozen=True, slots=True)
class GoodsSold:
    """A sale; ``average_paid`` is the game's average price paid, 0 for goods not bought."""

    at: datetime
    market_id: int
    commodity: Commodity
    count: int
    unit_price: int
    total: int
    average_paid: int

    @property
    def bought(self) -> bool:
        return self.average_paid > 0

    @property
    def profit(self) -> int:
        return (self.unit_price - self.average_paid) * self.count


@dataclass(frozen=True, slots=True)
class Docked:
    at: datetime
    market: Market


@dataclass(frozen=True, slots=True)
class Undocked:
    at: datetime


@dataclass(frozen=True, slots=True)
class GameLoaded:
    """The game (or EDMC) started: docked at a market, or in flight since an unknown time."""

    at: datetime
    market: Market | None


@dataclass(frozen=True, slots=True)
class CargoEjected:
    at: datetime
    commodity: Commodity
    count: int


@dataclass(frozen=True, slots=True)
class CargoInventory:
    """What the ship carries, as the game restates it after every change."""

    at: datetime
    tons: tuple[tuple[Commodity, int], ...]


@dataclass(frozen=True, slots=True)
class CommanderDied:
    at: datetime


@dataclass(frozen=True, slots=True)
class GameClosed:
    at: datetime


type Fact = (
    GoodsBought
    | GoodsSold
    | Docked
    | Undocked
    | GameLoaded
    | CargoEjected
    | CargoInventory
    | CommanderDied
    | GameClosed
)


def parse_entry(entry: Entry) -> Fact | None:
    """Return the trade fact carried by a journal entry, or ``None`` if irrelevant."""
    return translate(entry, _PARSERS)


def _count(entry: Entry) -> int:
    count = required(entry, "Count", int)
    if count <= 0:
        raise MalformedEntryError("Count")
    return count


def _bought(entry: Entry, at: datetime) -> GoodsBought:
    return GoodsBought(
        at=at,
        market_id=required(entry, "MarketID", int),
        commodity=commodity(entry, "Type"),
        count=_count(entry),
        unit_price=required(entry, "BuyPrice", int),
        total=required(entry, "TotalCost", int),
    )


def _sold(entry: Entry, at: datetime) -> GoodsSold:
    return GoodsSold(
        at=at,
        market_id=required(entry, "MarketID", int),
        commodity=commodity(entry, "Type"),
        count=_count(entry),
        unit_price=required(entry, "SellPrice", int),
        total=required(entry, "TotalSale", int),
        average_paid=optional(entry, "AvgPricePaid", int) or 0,
    )


def _market(entry: Entry) -> Market:
    return Market(
        market_id=required(entry, "MarketID", int),
        station=required(entry, "StationName", str),
        system=optional(entry, "StarSystem", str),
    )


def _docked(entry: Entry, at: datetime) -> Docked:
    return Docked(at, _market(entry))


def _undocked(_entry: Entry, at: datetime) -> Undocked:
    return Undocked(at)


def _loaded(entry: Entry, at: datetime) -> GameLoaded:
    docked = optional(entry, "Docked", bool) and "MarketID" in entry
    return GameLoaded(at, _market(entry) if docked else None)


def _ejected(entry: Entry, at: datetime) -> CargoEjected:
    return CargoEjected(at, commodity(entry, "Type"), _count(entry))


def _cargo(entry: Entry, at: datetime) -> CargoInventory | None:
    if entry.get("Vessel") != "Ship" or "Inventory" not in entry:
        return None
    return CargoInventory(
        at,
        tuple(
            (commodity(item, "Name"), required(item, "Count", int))
            for item in items(entry, "Inventory")
        ),
    )


def _died(_entry: Entry, at: datetime) -> CommanderDied:
    return CommanderDied(at)


def _closed(_entry: Entry, at: datetime) -> GameClosed:
    return GameClosed(at)


_PARSERS: dict[str, Parser[Fact | None]] = {
    "MarketBuy": _bought,
    "MarketSell": _sold,
    "Docked": _docked,
    "Undocked": _undocked,
    "Location": _loaded,
    "StartUp": _loaded,  # synthetic event from EDMC when started with the game running
    "EjectCargo": _ejected,
    "Cargo": _cargo,
    "Died": _died,
    "Shutdown": _closed,
    "ShutDown": _closed,  # synthetic event from EDMC when the game crashed
}
