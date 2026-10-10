"""The on-foot part of engineering (ADR 0027): the ship locker, the backpack, the equipment.

The **inventory** is the last ship locker the game stated, plus the backpack:
each statement replaces its place as a whole, the backpack's changes apply
between two statements. Boarding moves the backpack into the locker until the
game restates it; a death empties the backpack. Mission items are counted
apart: they are not the player's. Consumables are held, never counted towards
goals.

At the player's own fleet carrier (ADR 0029), the change of the player's own
materials between two statements of the locker is a **move** to the carrier
(fewer) or from it (more): the journal writes no event for it. A move is
counted nowhere: the carrier's content is not known.

The **equipment** is every suit and weapon the journal showed, by id, as last
shown: its class and its modifications.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from edrockmaster.domain.engineering.catalogue import OnFootKind
from edrockmaster.domain.engineering.on_foot_journal import Stock, Suit, Weapon

type Equipment = Suit | Weapon

type _Place = Counter[tuple[str, bool]]
"""Count by (symbol, held for a mission)."""


@dataclass(frozen=True, slots=True)
class OnFootHolding:
    symbol: str
    kind: OnFootKind
    locker: int
    """The player's own, in the ship locker."""
    backpack: int
    """The player's own, in the backpack."""
    mission: int
    """Held for missions, in either place."""


@dataclass(frozen=True, slots=True)
class CarrierMove:
    """What moved between the ship locker and the player's carrier during one docking."""

    docked_at: datetime
    at: datetime
    """The last statement of the locker that showed a move."""
    changes: Mapping[str, int]
    """By symbol: fewer in the locker (moved to the carrier), or more (taken from it)."""


class OnFoot:
    def __init__(self) -> None:
        self._locker: _Place | None = None
        self._backpack: _Place = Counter()
        self._kinds: dict[str, OnFootKind] = {}
        self._equipment: dict[int, Equipment] = {}
        self._carrier: int | None = None
        self._docked: tuple[datetime, int] | None = None
        """Since when, and at which market, the ship is docked."""
        self._moves: list[CarrierMove] = []

    @property
    def known(self) -> bool:
        return self._locker is not None

    def inventory(self) -> tuple[OnFootHolding, ...] | None:
        """Every material held, by symbol; ``None`` until the game states the locker."""
        if self._locker is None:
            return None
        symbols = sorted({symbol for symbol, _ in self._locker + self._backpack})
        return tuple(
            OnFootHolding(
                symbol,
                self._kinds[symbol],
                self._locker[(symbol, False)],
                self._backpack[(symbol, False)],
                self._locker[(symbol, True)] + self._backpack[(symbol, True)],
            )
            for symbol in symbols
        )

    def held(self) -> Mapping[str, int]:
        """What counts towards goals: the player's own materials, consumables aside."""
        return dict(self._own(self._locker or Counter()) + self._own(self._backpack))

    @property
    def carrier_moves(self) -> tuple[CarrierMove, ...]:
        return tuple(self._moves)

    @property
    def equipment(self) -> Mapping[int, Equipment]:
        return dict(self._equipment)

    # The places

    def state_locker(self, at: datetime, stock: Iterable[Stock]) -> None:
        locker = self._place(stock)
        if self._locker is not None and self._docked is not None:
            docked_at, market = self._docked
            if market == self._carrier:
                self._move(docked_at, at, self._own(locker), self._own(self._locker))
        self._locker = locker

    # The player's carrier

    def know_carrier(self, carrier_id: int) -> None:
        self._carrier = carrier_id

    def dock(self, at: datetime, market_id: int) -> None:
        self._docked = (at, market_id)

    def undock(self) -> None:
        self._docked = None

    def state_backpack(self, stock: Iterable[Stock]) -> None:
        self._backpack = self._place(stock)

    def change_backpack(
        self, added: Iterable[Stock], removed: Iterable[Stock]
    ) -> Counter[OnFootKind]:
        """Apply a change; return the player's own materials it brought in, by kind."""
        gained: Counter[OnFootKind] = Counter()
        for stock in added:
            self._kinds[stock.symbol] = stock.kind
            self._backpack[(stock.symbol, stock.mission)] += stock.count
            if _counted(stock):
                gained[stock.kind] += stock.count
        for stock in removed:
            self._kinds[stock.symbol] = stock.kind
            self._backpack[(stock.symbol, stock.mission)] -= stock.count
        self._backpack = +self._backpack
        return gained

    def board(self) -> None:
        if self._locker is not None:
            self._locker += self._backpack
        self._backpack = Counter()

    def die(self) -> int:
        """Empty the backpack; return how many of the player's own materials were lost."""
        lost = sum(self._own(self._backpack).values())
        self._backpack = Counter()
        return lost

    # The equipment

    def show(self, *pieces: Equipment) -> None:
        for piece in pieces:
            self._equipment[piece.id] = piece

    def sold(self, id_: int) -> None:
        self._equipment.pop(id_, None)

    def _move(
        self, docked_at: datetime, at: datetime, after: Counter[str], before: Counter[str]
    ) -> None:
        changes = Counter(after)
        changes.subtract(before)
        moved = {symbol: count for symbol, count in sorted(changes.items()) if count}
        if not moved:
            return
        if self._moves and self._moves[-1].docked_at == docked_at:
            total = Counter(self._moves[-1].changes)
            total.update(moved)
            moved = {symbol: count for symbol, count in sorted(total.items()) if count}
            self._moves[-1] = CarrierMove(docked_at, at, moved)
        else:
            self._moves.append(CarrierMove(docked_at, at, moved))

    def _own(self, place: _Place) -> Counter[str]:
        """The player's own materials of a place, consumables aside, by symbol."""
        counts: Counter[str] = Counter()
        for (symbol, mission), count in place.items():
            if not mission and self._kinds[symbol] is not OnFootKind.CONSUMABLE:
                counts[symbol] += count
        return counts

    def _place(self, stock: Iterable[Stock]) -> _Place:
        place: _Place = Counter()
        for item in stock:
            self._kinds[item.symbol] = item.kind
            place[(item.symbol, item.mission)] += item.count
        return +place


def _counted(stock: Stock) -> bool:
    return not stock.mission and stock.kind is not OnFootKind.CONSUMABLE
