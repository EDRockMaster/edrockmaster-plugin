"""Where to sell: the markets that buy a commodity (ADR 0040).

The filters a source cannot apply are applied here, so that what the player
sees does not depend on the source that answered.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

DEFAULT_MAX_DISTANCE = 50.0
"""Light years around the reference system."""

MAX_DISTANCE = 500.0
"""The farthest a source searches (Ardent)."""

DEFAULT_MAX_AGE = timedelta(days=30)


class PadSize(Enum):
    """A landing pad, small to large."""

    SMALL = 1
    MEDIUM = 2
    LARGE = 3

    @classmethod
    def from_number(cls, number: int | None) -> PadSize | None:
        try:
            return cls(number) if number is not None else None
        except ValueError:
            return None

    def fits(self, needed: PadSize) -> bool:
        """Whether a ship that needs ``needed`` can land on this pad."""
        return self.value >= needed.value


@dataclass(frozen=True, slots=True)
class MarketOffer:
    """A market that buys a commodity, as a source knows it."""

    station: str
    system: str
    market_id: int
    station_type: str
    pad: PadSize | None
    """The largest pad; ``None`` when the source does not say."""
    arrival: float | None
    """Light seconds from the system's arrival point."""
    price: int
    """Credits per tonne the market pays."""
    demand: int
    distance: float
    """Light years from the reference system."""
    updated: datetime
    """When the source last saw the price."""
    is_carrier: bool


@dataclass(frozen=True, slots=True)
class SaleQuery:
    """Where to sell a commodity around a system."""

    commodity: str
    """The commodity's key (``Commodity.key``)."""
    reference: str
    max_distance: float = DEFAULT_MAX_DISTANCE
    needed_pad: PadSize | None = None
    """The pad the ship needs; ``None``: any market."""
    carriers: bool = False
    """Whether fleet carriers count: their orders move and close."""
    max_age: timedelta = DEFAULT_MAX_AGE

    def __post_init__(self) -> None:
        commodity = self.commodity.strip().lower()
        reference = self.reference.strip()
        if not commodity:
            raise ValueError("a commodity is needed")
        if not reference:
            raise ValueError("a reference system is needed")
        if not 0 < self.max_distance <= MAX_DISTANCE:
            raise ValueError(f"the distance must be within {MAX_DISTANCE:.0f} light years")
        object.__setattr__(self, "commodity", commodity)
        object.__setattr__(self, "reference", reference)


def select_offers(
    offers: Iterable[MarketOffer], query: SaleQuery, now: datetime
) -> tuple[MarketOffer, ...]:
    """The offers the query accepts, the best price first."""

    def accepted(offer: MarketOffer) -> bool:
        if offer.distance > query.max_distance or now - offer.updated > query.max_age:
            return False
        if offer.is_carrier and not query.carriers:
            return False
        if query.needed_pad is None:
            return True
        return offer.pad is not None and offer.pad.fits(query.needed_pad)

    return tuple(
        sorted(
            (offer for offer in offers if accepted(offer)),
            key=lambda offer: (-offer.price, offer.distance),
        )
    )
