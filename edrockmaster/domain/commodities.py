"""Commodities as they appear in the game journal, and the markets that trade them.

A market offer serves both ways (ADR 0047): the markets that buy a commodity, where
the player sells it, and those that sell it, where the player buys it. The filters a
source cannot apply are applied here (ADR 0040), so that what the player sees does
not depend on the source that answered.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from edrockmaster.domain.ships import PadSize

_SYMBOL_PREFIX = "$"
_SYMBOL_SUFFIXES = (";", "_name")


@dataclass(frozen=True, slots=True)
class Commodity:
    """A commodity, identified by a stable key whatever the journal spelling.

    The journal names the same commodity ``$painite_name;``, ``Painite`` or
    ``painite`` depending on the event. ``key`` is the normalised form; the
    localised name only serves for display and is not part of the identity.
    """

    key: str
    localised: str | None = field(default=None, compare=False)

    @classmethod
    def from_symbol(cls, symbol: str, localised: str | None = None) -> Commodity:
        key = symbol.strip().lower()
        key = key.removeprefix(_SYMBOL_PREFIX)
        for suffix in _SYMBOL_SUFFIXES:
            key = key.removesuffix(suffix)
        if not key:
            raise ValueError("empty commodity symbol")
        return cls(key=key, localised=localised or None)


LIMPET = Commodity.from_symbol("drones")

REFINED_COMMODITIES = frozenset(
    Commodity(key)
    for key in (
        # metals
        "aluminium",
        "beryllium",
        "bismuth",
        "cobalt",
        "copper",
        "gallium",
        "gold",
        "indium",
        "lanthanum",
        "lithium",
        "osmium",
        "palladium",
        "platinum",
        "praseodymium",
        "samarium",
        "silver",
        "tantalum",
        "thallium",
        "thorium",
        "titanium",
        "uranium",
        # minerals
        "alexandrite",
        "bauxite",
        "benitoite",
        "bertrandite",
        "bromellite",
        "coltan",
        "cryolite",
        "gallite",
        "goslarite",
        "grandidierite",
        "indite",
        "jadeite",
        "lepidolite",
        "lithiumhydroxide",
        "lowtemperaturediamond",
        "methaneclathrate",
        "methanolmonohydratecrystals",
        "moissanite",
        "monazite",
        "musgravite",
        "opal",
        "painite",
        "pyrophyllite",
        "rhodplumsite",
        "rutile",
        "serendibite",
        "taaffeite",
        "uraninite",
        # chemicals
        "hydrogenperoxide",
        "liquidoxygen",
        "tritium",
        "water",
    )
)
"""Commodities a mining refinery produces. Many are traded too: what tells a mined
ton from a bought one is the price paid, not the commodity."""


DEFAULT_MAX_DISTANCE = 50.0
"""Light years around the reference system."""

MAX_DISTANCE = 500.0
"""The farthest a source searches (Ardent)."""

DEFAULT_MAX_AGE = timedelta(days=30)


class Side(Enum):
    """What the player does at the market."""

    BUY = "buy"
    """The player buys: the markets that sell the commodity (their stock)."""
    SELL = "sell"
    """The player sells: the markets that buy the commodity (their demand)."""


@dataclass(frozen=True, slots=True)
class MarketOffer:
    """A market that buys or sells a commodity, as a source knows it."""

    station: str
    system: str
    market_id: int
    station_type: str
    pad: PadSize | None
    """The largest pad; ``None`` when the source does not say."""
    arrival: float | None
    """Light seconds from the system's arrival point."""
    price: int
    """Credits per tonne: what the market pays, or what it asks."""
    volume: int
    """Tonnes: its demand where it buys, its stock where it sells."""
    distance: float
    """Light years from the reference system."""
    updated: datetime
    """When the source last saw the price."""
    is_carrier: bool


@dataclass(frozen=True, slots=True)
class MarketQuery:
    """Where to buy or sell a commodity around a system."""

    side: Side
    commodity: str
    """The commodity's key (``Commodity.key``)."""
    reference: str
    max_distance: float = DEFAULT_MAX_DISTANCE
    needed_pad: PadSize | None = None
    """The pad the ship needs; ``None``: any market."""
    carriers: bool = False
    """Whether fleet carriers count: their orders move and close."""
    max_age: timedelta = DEFAULT_MAX_AGE
    min_volume: int = 1
    """The least demand or stock worth the trip, in tonnes."""

    def __post_init__(self) -> None:
        commodity = self.commodity.strip().lower()
        reference = self.reference.strip()
        if not commodity:
            raise ValueError("a commodity is needed")
        if not reference:
            raise ValueError("a reference system is needed")
        if not 0 < self.max_distance <= MAX_DISTANCE:
            raise ValueError(f"the distance must be within {MAX_DISTANCE:.0f} light years")
        if self.min_volume < 1:
            raise ValueError("the volume must be one tonne at least")
        object.__setattr__(self, "commodity", commodity)
        object.__setattr__(self, "reference", reference)


def select_offers(
    offers: Iterable[MarketOffer], query: MarketQuery, now: datetime
) -> tuple[MarketOffer, ...]:
    """The offers the query accepts, the best price first: the highest a market pays, or the
    lowest it asks."""

    def accepted(offer: MarketOffer) -> bool:
        if offer.distance > query.max_distance or now - offer.updated > query.max_age:
            return False
        if offer.volume < query.min_volume:
            return False
        if offer.is_carrier and not query.carriers:
            return False
        if query.needed_pad is None:
            return True
        return offer.pad is not None and offer.pad.fits(query.needed_pad)

    best = -1 if query.side is Side.SELL else 1
    return tuple(
        sorted(
            (offer for offer in offers if accepted(offer)),
            key=lambda offer: (best * offer.price, offer.distance),
        )
    )
