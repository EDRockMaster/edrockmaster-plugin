"""The market of the station the commander is docked at (ADR 0047).

The game writes a station's market when the player opens it (``Market.json``).
It is the market of that station while the commander stays docked there: it goes
once they undock, dock elsewhere, die or leave the game. Only the commodities the
station sells (a stock) or buys (a demand) are kept: the file lists every
commodity, most of them not traded there.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from edrockmaster.domain.trade.journal import (
    CommanderDied,
    Docked,
    Fact,
    GameClosed,
    GameLoaded,
    Market,
    MarketLine,
    MarketRead,
    Undocked,
)


@dataclass(frozen=True, slots=True)
class StationMarket:
    market: Market
    read_at: datetime
    lines: tuple[MarketLine, ...]


@dataclass(frozen=True, slots=True)
class StationMarketChanged:
    market: StationMarket | None
    """``None``: the commander left the station."""


class StationMarketTracker:
    def __init__(self) -> None:
        self.market: StationMarket | None = None

    def handle(self, fact: Fact) -> list[StationMarketChanged]:
        match fact:
            case MarketRead(at=at, market=market, lines=lines):
                traded = tuple(line for line in lines if line.stock > 0 or line.demand > 0)
                self.market = StationMarket(market, at, traded)
                return [StationMarketChanged(self.market)]
            case Docked(market=market) | GameLoaded(market=market) if self._at(market):
                return []
            case Docked() | GameLoaded() | Undocked() | CommanderDied() | GameClosed():
                return self._left()
            case _:
                return []

    def _at(self, market: Market | None) -> bool:
        return market is not None and self.market is not None and market == self.market.market

    def _left(self) -> list[StationMarketChanged]:
        if self.market is None:
            return []
        self.market = None
        return [StationMarketChanged(None)]
