"""What the mining cargo is worth at the best markets around (ADR 0040)."""

from __future__ import annotations

from dataclasses import dataclass

from edrockmaster.domain.commodities import MarketOffer


@dataclass(frozen=True, slots=True)
class CargoLine:
    """A commodity of the cargo, and the best market found for it."""

    commodity: str
    tons: int
    best: MarketOffer | None
    """``None``: no market found, or the source gave nothing."""

    @property
    def value(self) -> int | None:
        return self.tons * self.best.price if self.best is not None else None


@dataclass(frozen=True, slots=True)
class CargoEstimate:
    lines: tuple[CargoLine, ...]

    @property
    def total(self) -> int:
        """What the priced lines are worth together."""
        return sum(line.value for line in self.lines if line.value is not None)
