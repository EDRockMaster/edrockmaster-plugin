"""Trade sessions: profit, routes and flight time (ADR 0014).

``TradeTracker`` is the aggregate root of the trade context. Durations come from
journal timestamps, never from the wall clock, so that a replayed journal yields
the same statistics.

A **trade session** starts with the first purchase or the first sale of bought
goods; it ends on game close, death or reset. The profit of a sale is the game's
own: ``(SellPrice - AvgPricePaid) * Count``, even for goods bought before EDMC
started.

The active time is the **flight time**. A **leg** runs from undocking to the
next docking, and counts once a trade (a purchase, or a sale of bought goods)
follows it in the session: the flight to the first market, and the flights
after the last trade, do not count. A stop on the way, with no trade, is part
of the flight. Time docked never counts.

The tracker keeps what it saw bought, per commodity, beyond the sessions: the
cargo is still on board after a reset. Its cost is the average price paid, and
the market of the last purchase is the origin of the route. Bought goods
ejected or lost with the ship are a loss, at that cost; goods bought before
EDMC started have an unknown cost and origin.

Goods sold that were not bought (an average price paid of 0) are in no profit
and no rate: **refined commodities** when a refinery produces them (their
profit belongs to mining), **other goods** otherwise.

**Transfers** with a fleet carrier (ADR 0019) are trade moves, like purchases
and sales: a deposit or a withdrawal starts a session and counts the legs it
follows. They earn nothing. The goods keep their cost and origin at the
carrier, so that a ship destroyed after a deposit loses nothing it deposited,
and a withdrawal brings them back on board. What the tracker knows a carrier
holds is not its stock: the carrier trades while the commander is away.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import assert_never

from edrockmaster.domain.commodities import REFINED_COMMODITIES, Commodity
from edrockmaster.domain.trade.journal import (
    CargoEjected,
    CargoInventory,
    CargoTransferred,
    CommanderDied,
    Docked,
    Fact,
    GameClosed,
    GameLoaded,
    GoodsBought,
    GoodsSold,
    Market,
    Transfer,
    TransferDirection,
    Undocked,
)


class TransferKind(Enum):
    DEPOSIT = "deposit"
    """From the ship to a fleet carrier."""
    WITHDRAWAL = "withdrawal"
    """From a fleet carrier to the ship."""


class TradeEndReason(Enum):
    GAME_CLOSED = "game_closed"
    DIED = "died"
    MANUAL = "manual"


def _per_hour(amount: float, duration: timedelta) -> float:
    hours = duration.total_seconds() / 3600
    return amount / hours if hours else 0.0


@dataclass(frozen=True, slots=True)
class GoodsTally:
    tons: int = 0
    credits: int = 0

    def __add__(self, other: GoodsTally) -> GoodsTally:
        return GoodsTally(self.tons + other.tons, self.credits + other.credits)


@dataclass(frozen=True, slots=True)
class RouteStats:
    """One commodity bought at one market and sold at another; origin ``None`` if unknown."""

    commodity: Commodity
    origin: Market | None
    destination: Market
    tons: int
    profit: int
    sales: int

    @property
    def profit_per_ton(self) -> float:
        return self.profit / self.tons if self.tons else 0.0


@dataclass(frozen=True, slots=True)
class TransferStats:
    """One commodity moved one way between the ship and fleet carriers."""

    commodity: Commodity
    kind: TransferKind
    tons: int
    transfers: int


@dataclass(frozen=True, slots=True)
class TradeStats:
    started_at: datetime
    flight_time: timedelta
    routes: tuple[RouteStats, ...]
    """In the order of their first sale."""
    losses: int
    refined: GoodsTally
    """Mined commodities sold: their profit belongs to mining."""
    other: GoodsTally
    """Anything else sold that was not bought: salvage, mission rewards."""
    cargo: GoodsTally
    """Bought goods on board, at the price paid, as far as the tracker saw them bought."""
    transfers: tuple[TransferStats, ...] = ()
    """With fleet carriers, in the order of the first transfer of each."""

    @property
    def tons_sold(self) -> int:
        return sum(route.tons for route in self.routes)

    @property
    def profit(self) -> int:
        return sum(route.profit for route in self.routes) - self.losses

    @property
    def profit_per_hour(self) -> float:
        return _per_hour(self.profit, self.flight_time)

    @property
    def tons_per_hour(self) -> float:
        return _per_hour(self.tons_sold, self.flight_time)


@dataclass(frozen=True, slots=True)
class TradeStarted:
    at: datetime


@dataclass(frozen=True, slots=True)
class TradeUpdated:
    stats: TradeStats


@dataclass(frozen=True, slots=True)
class TradeEnded:
    at: datetime
    reason: TradeEndReason
    stats: TradeStats


type TradeNotification = TradeStarted | TradeUpdated | TradeEnded


@dataclass(slots=True)
class _Lot:
    """Bought goods of one commodity, as far as the tracker saw them."""

    commodity: Commodity
    origin: Market
    tons: int = 0
    cost: int = 0

    def take(self, tons: int) -> _Lot:
        """Remove up to ``tons``, at the average price paid; the part removed is returned."""
        taken = min(tons, self.tons)
        cost = self.cost * taken // self.tons if taken else 0
        self.tons -= taken
        self.cost -= cost
        return _Lot(self.commodity, self.origin, taken, cost)


class _Hold:
    """Bought goods of known cost, per commodity: the ship's, or those left at a carrier."""

    def __init__(self) -> None:
        self._lots: dict[Commodity, _Lot] = {}

    def lot(self, commodity: Commodity) -> _Lot | None:
        return self._lots.get(commodity)

    def lots(self) -> list[_Lot]:
        return list(self._lots.values())

    def tally(self) -> GoodsTally:
        return sum((GoodsTally(lot.tons, lot.cost) for lot in self._lots.values()), GoodsTally())

    def put(self, goods: _Lot) -> None:
        """Add goods; the last origin wins, and a localised name over a bare symbol."""
        lot = self._lots.get(goods.commodity)
        if lot is None:
            lot = self._lots[goods.commodity] = _Lot(goods.commodity, goods.origin)
        lot.origin = goods.origin
        if goods.commodity.localised:
            lot.commodity = goods.commodity
        lot.tons += goods.tons
        lot.cost += goods.cost

    def take(self, commodity: Commodity, tons: int) -> _Lot | None:
        lot = self._lots.get(commodity)
        if lot is None:
            return None
        taken = lot.take(tons)
        if not lot.tons:
            del self._lots[commodity]
        return taken if taken.tons else None

    def cost_of(self, commodity: Commodity, tons: int) -> int:
        taken = self.take(commodity, tons)
        return taken.cost if taken else 0


@dataclass(slots=True)
class _Route:
    commodity: Commodity
    origin: Market | None
    destination: Market
    tons: int = 0
    profit: int = 0
    sales: int = 0

    def stats(self) -> RouteStats:
        return RouteStats(
            self.commodity, self.origin, self.destination, self.tons, self.profit, self.sales
        )


type _RouteKey = tuple[Commodity, int | None, int]


class TradeSession:
    """A running trade session. Mutated only through ``TradeTracker``."""

    def __init__(self, started_at: datetime) -> None:
        self.started_at = started_at
        self._flight = timedelta(0)
        self._routes: dict[_RouteKey, _Route] = {}
        self._transfers: dict[tuple[Commodity, TransferKind], TransferStats] = {}
        self._losses = 0
        self._refined = GoodsTally()
        self._other = GoodsTally()

    def stats(self, cargo: GoodsTally) -> TradeStats:
        return TradeStats(
            started_at=self.started_at,
            flight_time=self._flight,
            routes=tuple(route.stats() for route in self._routes.values()),
            losses=self._losses,
            refined=self._refined,
            other=self._other,
            cargo=cargo,
            transfers=tuple(self._transfers.values()),
        )

    def fly(self, duration: timedelta) -> None:
        self._flight += duration

    def sell(
        self, sale: GoodsSold, commodity: Commodity, origin: Market | None, destination: Market
    ) -> None:
        key = (commodity, origin.market_id if origin else None, destination.market_id)
        route = self._routes.setdefault(key, _Route(commodity, origin, destination))
        route.tons += sale.count
        route.profit += sale.profit
        route.sales += 1

    def sell_unbought(self, sale: GoodsSold) -> None:
        tally = GoodsTally(sale.count, sale.total)
        if sale.commodity in REFINED_COMMODITIES:
            self._refined += tally
        else:
            self._other += tally

    def transfer(self, commodity: Commodity, kind: TransferKind, tons: int) -> None:
        moved = self._transfers.get((commodity, kind), TransferStats(commodity, kind, 0, 0))
        self._transfers[commodity, kind] = TransferStats(
            moved.commodity, kind, moved.tons + tons, moved.transfers + 1
        )

    def lose(self, cost: int) -> None:
        self._losses += cost


type _CarrierKey = int | None
"""The market id of a fleet carrier, or ``None`` when the deposit's carrier is unknown."""


class TradeTracker:
    """Aggregate root: follows the commander's markets, flights, cargo and trade."""

    def __init__(self) -> None:
        self._session: TradeSession | None = None
        self._market: Market | None = None
        """Where the commander is docked, if known."""
        self._undocked_at: datetime | None = None
        self._flown = timedelta(0)
        """Legs flown since the last trade: they count once a trade follows."""
        self._hold = _Hold()
        self._carriers: dict[_CarrierKey, _Hold] = {}

    @property
    def session(self) -> TradeSession | None:
        return self._session

    @property
    def stats(self) -> TradeStats | None:
        return self._session.stats(self._hold.tally()) if self._session else None

    def handle(self, fact: Fact) -> list[TradeNotification]:
        match fact:
            case GoodsBought():
                return self._on_purchase(fact)
            case GoodsSold():
                return self._on_sale(fact)
            case CargoTransferred():
                return self._on_transfer(fact)
            case Docked() | Undocked() | GameLoaded():
                self._on_move(fact)
                return []
            case CargoEjected() | CargoInventory():
                return self._on_cargo(fact)
            case CommanderDied() | GameClosed():
                return self._on_exit(fact)
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(fact)

    def reset(self, at: datetime) -> TradeEnded | None:
        return self._end(at, TradeEndReason.MANUAL)

    def _market_named(self, market_id: int) -> Market:
        """The market of an event, with the names of the docking when it is the same."""
        if self._market is not None and self._market.market_id == market_id:
            return self._market
        return Market(market_id)

    def _on_move(self, fact: Docked | Undocked | GameLoaded) -> None:
        match fact:
            case Docked(at=at, market=market):
                if self._undocked_at is not None:
                    self._flown += max(at - self._undocked_at, timedelta(0))
                self._undocked_at, self._market = None, market
            case Undocked(at=at):
                self._undocked_at, self._market = at, None
            case GameLoaded(at=at, market=market):
                # In flight since an unknown time: the leg counts from now
                self._undocked_at = None if market else at
                self._market = market
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(fact)

    def _trade(self, at: datetime) -> tuple[TradeSession, list[TradeNotification]]:
        """The session a trade belongs to, started if needed, with the legs it follows."""
        if self._session is None:
            self._session = TradeSession(at)
            self._flown = timedelta(0)  # the flight to the first market
            return self._session, [TradeStarted(at)]
        self._session.fly(self._flown)
        self._flown = timedelta(0)
        return self._session, []

    def _updated(self, session: TradeSession) -> TradeUpdated:
        return TradeUpdated(session.stats(self._hold.tally()))

    def _on_purchase(self, purchase: GoodsBought) -> list[TradeNotification]:
        market = self._market_named(purchase.market_id)
        self._hold.put(_Lot(purchase.commodity, market, purchase.count, purchase.total))
        session, notifications = self._trade(purchase.at)
        return [*notifications, self._updated(session)]

    def _on_sale(self, sale: GoodsSold) -> list[TradeNotification]:
        if not sale.bought:
            if self._session is None:
                return []
            self._session.sell_unbought(sale)
            return [self._updated(self._session)]
        lot = self._hold.lot(sale.commodity)
        # The purchase may have named the commodity in the game's language, not the sale
        commodity, origin = (lot.commodity, lot.origin) if lot else (sale.commodity, None)
        self._hold.take(sale.commodity, sale.count)
        session, notifications = self._trade(sale.at)
        session.sell(sale, commodity, origin, self._market_named(sale.market_id))
        return [*notifications, self._updated(session)]

    def _on_transfer(self, fact: CargoTransferred) -> list[TradeNotification]:
        moves = [(transfer, kind) for transfer in fact.transfers if (kind := self._kind(transfer))]
        if not moves:
            return []
        carrier = self._carriers.setdefault(
            self._market.market_id if self._market else None, _Hold()
        )
        session, notifications = self._trade(fact.at)
        for transfer, kind in moves:
            source, target = (
                (self._hold, carrier) if kind is TransferKind.DEPOSIT else (carrier, self._hold)
            )
            if goods := source.take(transfer.commodity, transfer.count):
                target.put(goods)
            session.transfer(transfer.commodity, kind, transfer.count)
        return [*notifications, self._updated(session)]

    def _kind(self, transfer: Transfer) -> TransferKind | None:
        """A deposit, a withdrawal, or ``None`` for a transfer with an SRV."""
        match transfer.direction:
            case TransferDirection.TO_CARRIER:
                return TransferKind.DEPOSIT
            case TransferDirection.TO_SHIP if self._market and self._market.fleet_carrier:
                return TransferKind.WITHDRAWAL
            case _:
                return None

    def _on_loss(self, cost: int) -> list[TradeNotification]:
        if self._session is None or not cost:
            return []
        self._session.lose(cost)
        return [self._updated(self._session)]

    def _on_cargo(self, fact: CargoEjected | CargoInventory) -> list[TradeNotification]:
        if isinstance(fact, CargoEjected):
            return self._on_loss(self._hold.cost_of(fact.commodity, fact.count))
        # Goods may leave without a sale (a mission): never hold more than on board
        on_board = dict(fact.tons)
        for lot in self._hold.lots():
            self._hold.take(lot.commodity, lot.tons - min(lot.tons, on_board.get(lot.commodity, 0)))
        return []

    def _on_exit(self, fact: CommanderDied | GameClosed) -> list[TradeNotification]:
        if isinstance(fact, GameClosed):
            return self._ended(fact.at, TradeEndReason.GAME_CLOSED)
        return self._on_death(fact.at)

    def _on_death(self, at: datetime) -> list[TradeNotification]:
        """The ship is lost with its cargo, and the leg in flight ends there."""
        self._undocked_at, self._market = None, None
        lost = sum(self._hold.cost_of(lot.commodity, lot.tons) for lot in self._hold.lots())
        return self._on_loss(lost) + self._ended(at, TradeEndReason.DIED)

    def _ended(self, at: datetime, reason: TradeEndReason) -> list[TradeNotification]:
        ended = self._end(at, reason)
        return [ended] if ended else []

    def _end(self, at: datetime, reason: TradeEndReason) -> TradeEnded | None:
        if self._session is None:
            return None
        ended = TradeEnded(at=at, reason=reason, stats=self._session.stats(self._hold.tally()))
        self._session = None
        self._flown = timedelta(0)
        return ended
