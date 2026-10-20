"""Trade routes (ADR 0047, ADR 0057): from a station, the hops a source plans, each with what to
buy there and sell at the next station, and the profit it makes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from edrockmaster.domain.ships import PadSize

MAX_HOPS = 10
"""As many as Spansh's site lets one ask."""
DEFAULT_HOPS = 3
DEFAULT_HOP_DISTANCE = 30.0
DEFAULT_PRICE_AGE = timedelta(days=2)


@dataclass(frozen=True, slots=True)
class RouteQuery:
    system: str
    station: str
    """Where the route starts."""
    cargo_capacity: int
    credits: int
    """What the player may spend on the first purchase."""
    max_hops: int = DEFAULT_HOPS
    max_hop_distance: float = DEFAULT_HOP_DISTANCE
    """Light years: the ship's jump range, or less."""
    needed_pad: PadSize | None = None
    max_price_age: timedelta = DEFAULT_PRICE_AGE
    planetary: bool = False
    carriers: bool = False
    """Whether fleet carriers count: their orders move and close."""

    def __post_init__(self) -> None:
        system, station = self.system.strip(), self.station.strip()
        if not system or not station:
            raise ValueError("a starting system and station are needed")
        if self.cargo_capacity < 1:
            raise ValueError("the cargo capacity must be one tonne at least")
        if self.credits < 0:
            raise ValueError("the credits cannot be negative")
        if not 1 <= self.max_hops <= MAX_HOPS:
            raise ValueError(f"the hops must be 1 to {MAX_HOPS}")
        if self.max_hop_distance <= 0:
            raise ValueError("the distance per hop must be above 0")
        if self.max_price_age <= timedelta(0):
            raise ValueError("the prices' age must be above 0")
        object.__setattr__(self, "system", system)
        object.__setattr__(self, "station", station)


@dataclass(frozen=True, slots=True)
class RouteStation:
    station: str
    system: str
    arrival: float | None
    """Light seconds from the system's arrival point."""
    prices_updated: datetime | None
    """When the source last saw the station's prices."""


@dataclass(frozen=True, slots=True)
class HopCommodity:
    name: str
    """As the source names it, in English."""
    tons: int
    buy_price: int
    """Credits per tonne at the hop's start."""
    sell_price: int
    """Credits per tonne at the hop's end."""
    profit: int
    """Credits per tonne."""

    @property
    def total_profit(self) -> int:
        return self.profit * self.tons


@dataclass(frozen=True, slots=True)
class RouteHop:
    source: RouteStation
    destination: RouteStation
    distance: float
    """Light years."""
    commodities: tuple[HopCommodity, ...]
    profit: int


@dataclass(frozen=True, slots=True)
class TradeRoute:
    hops: tuple[RouteHop, ...]

    @property
    def profit(self) -> int:
        return sum(hop.profit for hop in self.hops)
