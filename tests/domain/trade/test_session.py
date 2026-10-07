from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.domain.commodities import Commodity
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
from edrockmaster.domain.trade.session import (
    GoodsTally,
    RouteStats,
    TradeEnded,
    TradeEndReason,
    TradeNotification,
    TradeStarted,
    TradeStats,
    TradeTracker,
    TradeUpdated,
    TransferKind,
    TransferStats,
)

T0 = datetime(2026, 10, 4, 14, 0, tzinfo=UTC)
AMANO = Market(1, "Amano Terminal", "Col 359 Sector IL-X d1-126")
VERNE = Market(2, "Verne Venture", "Col 285 Sector ZE-A b29-3")
DEPOT = Market(3, "Tan Depot")
PALLADIUM = Commodity("palladium")
CMM = Commodity("cmmcomposite")
PAINITE = Commodity("painite")
SALVAGE = Commodity("wreckagecomponents")


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def dock(minutes: float, market: Market) -> Docked:
    return Docked(at(minutes), market)


def undock(minutes: float) -> Undocked:
    return Undocked(at(minutes))


def buy(
    minutes: float, market: Market, commodity: Commodity, count: int, price: int
) -> GoodsBought:
    return GoodsBought(at(minutes), market.market_id, commodity, count, price, count * price)


def sell(
    minutes: float, market: Market, commodity: Commodity, count: int, price: int, *, paid: int
) -> GoodsSold:
    return GoodsSold(at(minutes), market.market_id, commodity, count, price, count * price, paid)


def feed(tracker: TradeTracker, *facts: Fact) -> list[TradeNotification]:
    notifications: list[TradeNotification] = []
    for fact in facts:
        notifications += tracker.handle(fact)
    return notifications


def stats_of(tracker: TradeTracker) -> TradeStats:
    stats = tracker.stats
    assert stats is not None
    return stats


def round_trip(tracker: TradeTracker) -> None:
    """Palladium from Amano to Verne, 20 minutes of flight."""
    feed(
        tracker,
        dock(0, AMANO),
        buy(2, AMANO, PALLADIUM, 100, 5_000),
        undock(5),
        dock(25, VERNE),
        sell(26, VERNE, PALLADIUM, 100, 50_000, paid=5_000),
    )


def test_no_session_before_a_trade() -> None:
    tracker = TradeTracker()
    assert feed(tracker, dock(0, AMANO), undock(5), dock(25, VERNE)) == []
    assert tracker.session is None
    assert tracker.stats is None


def test_a_purchase_starts_the_session() -> None:
    tracker = TradeTracker()
    notifications = feed(tracker, dock(0, AMANO), buy(2, AMANO, PALLADIUM, 100, 5_000))
    assert notifications[0] == TradeStarted(at(2))
    assert isinstance(notifications[1], TradeUpdated)
    stats = notifications[1].stats
    assert stats.started_at == at(2)
    assert stats.cargo == GoodsTally(100, 500_000)
    assert (stats.profit, stats.tons_sold, stats.flight_time) == (0, 0, timedelta(0))


def test_a_sale_of_goods_bought_before_edmc_starts_the_session() -> None:
    tracker = TradeTracker()
    notifications = feed(tracker, dock(0, VERNE), sell(1, VERNE, PALLADIUM, 10, 50_000, paid=5_000))
    assert notifications[0] == TradeStarted(at(1))
    stats = stats_of(tracker)
    # The origin is unknown, the profit is the game's own
    assert stats.routes == (RouteStats(PALLADIUM, None, VERNE, 10, 450_000, 1),)
    assert stats.cargo == GoodsTally()


def test_profit_of_a_round_trip_and_the_route() -> None:
    tracker = TradeTracker()
    round_trip(tracker)
    stats = stats_of(tracker)
    [route] = stats.routes
    assert (route.commodity, route.origin, route.destination) == (PALLADIUM, AMANO, VERNE)
    assert (route.tons, route.profit, route.sales) == (100, 4_500_000, 1)
    assert route.profit_per_ton == 45_000
    assert route.destination.station == "Verne Venture"
    assert stats.profit == 4_500_000
    assert stats.cargo == GoodsTally()


def test_flight_time_counts_the_legs_followed_by_a_trade() -> None:
    tracker = TradeTracker()
    feed(tracker, undock(-30), dock(0, AMANO))  # the flight to the first market
    round_trip(tracker)
    assert stats_of(tracker).flight_time == timedelta(minutes=20)
    # Flying home after the last sale: no trade follows, it does not count
    feed(tracker, undock(30), dock(50, DEPOT))
    assert stats_of(tracker).flight_time == timedelta(minutes=20)


def test_a_stop_without_trade_is_part_of_the_flight() -> None:
    tracker = TradeTracker()
    feed(
        tracker,
        dock(0, AMANO),
        buy(2, AMANO, PALLADIUM, 100, 5_000),
        undock(5),
        dock(15, DEPOT),  # refuel, 10 minutes docked
        undock(25),
        dock(35, VERNE),
        sell(36, VERNE, PALLADIUM, 100, 50_000, paid=5_000),
    )
    assert stats_of(tracker).flight_time == timedelta(minutes=20)


def test_rates_over_the_flight_time() -> None:
    tracker = TradeTracker()
    round_trip(tracker)
    feed(
        tracker,
        buy(27, VERNE, CMM, 100, 5_000),
        undock(30),
        dock(40, AMANO),
        sell(42, AMANO, CMM, 100, 20_000, paid=5_000),
    )
    stats = stats_of(tracker)
    assert stats.flight_time == timedelta(minutes=30)
    assert stats.profit == 4_500_000 + 1_500_000
    assert stats.profit_per_hour == pytest.approx(12_000_000)
    assert stats.tons_per_hour == pytest.approx(400)
    assert [route.commodity for route in stats.routes] == [PALLADIUM, CMM]


def test_no_rate_without_flight() -> None:
    tracker = TradeTracker()
    feed(tracker, dock(0, VERNE), sell(1, VERNE, PALLADIUM, 10, 50_000, paid=5_000))
    stats = stats_of(tracker)
    assert (stats.profit_per_hour, stats.tons_per_hour) == (0.0, 0.0)


def test_sales_of_the_same_route_add_up() -> None:
    tracker = TradeTracker()
    round_trip(tracker)
    feed(
        tracker,
        undock(30),
        dock(50, AMANO),
        buy(51, AMANO, PALLADIUM, 50, 5_000),
        undock(52),
        dock(72, VERNE),
        sell(73, VERNE, PALLADIUM, 50, 50_000, paid=5_000),
    )
    [route] = stats_of(tracker).routes
    assert (route.tons, route.profit, route.sales) == (150, 6_750_000, 2)


def test_the_origin_is_the_market_of_the_last_purchase() -> None:
    tracker = TradeTracker()
    feed(
        tracker,
        dock(0, AMANO),
        buy(1, AMANO, PALLADIUM, 50, 5_000),
        undock(2),
        dock(10, DEPOT),
        buy(11, DEPOT, PALLADIUM, 50, 6_000),
        undock(12),
        dock(20, VERNE),
        sell(21, VERNE, PALLADIUM, 100, 50_000, paid=5_500),
    )
    [route] = stats_of(tracker).routes
    assert route.origin == DEPOT
    assert route.origin is not None
    assert route.origin.station == "Tan Depot"


def test_a_market_not_seen_docking_has_no_name() -> None:
    tracker = TradeTracker()
    feed(
        tracker,
        buy(1, AMANO, PALLADIUM, 10, 5_000),
        sell(2, VERNE, PALLADIUM, 10, 9_000, paid=5_000),
    )
    [route] = stats_of(tracker).routes
    assert route.origin == AMANO
    assert route.origin is not None
    assert route.origin.station is None
    assert route.destination == VERNE
    assert route.destination.station is None


def test_partial_sale_keeps_the_rest_at_the_price_paid() -> None:
    tracker = TradeTracker()
    feed(
        tracker,
        dock(0, AMANO),
        buy(1, AMANO, PALLADIUM, 100, 5_000),
        sell(2, AMANO, PALLADIUM, 40, 5_100, paid=5_000),
    )
    assert stats_of(tracker).cargo == GoodsTally(60, 300_000)


def test_selling_more_than_seen_bought_empties_the_hold() -> None:
    tracker = TradeTracker()
    feed(
        tracker,
        buy(1, AMANO, PALLADIUM, 10, 5_000),
        sell(2, VERNE, PALLADIUM, 30, 50_000, paid=5_000),
    )
    stats = stats_of(tracker)
    assert stats.cargo == GoodsTally()
    assert stats.routes[0].tons == 30


def test_refined_commodities_and_other_goods_are_apart() -> None:
    tracker = TradeTracker()
    round_trip(tracker)
    notifications = feed(
        tracker,
        sell(27, VERNE, PAINITE, 10, 300_000, paid=0),
        sell(28, VERNE, SALVAGE, 2, 10_000, paid=0),
    )
    assert all(isinstance(notification, TradeUpdated) for notification in notifications)
    stats = stats_of(tracker)
    assert stats.refined == GoodsTally(10, 3_000_000)
    assert stats.other == GoodsTally(2, 20_000)
    assert (stats.profit, stats.tons_sold) == (4_500_000, 100)
    assert len(stats.routes) == 1


def test_goods_not_bought_start_no_session() -> None:
    tracker = TradeTracker()
    assert feed(tracker, dock(0, VERNE), sell(1, VERNE, PAINITE, 10, 300_000, paid=0)) == []
    assert tracker.session is None


def test_a_sale_of_goods_not_bought_does_not_count_the_flight() -> None:
    tracker = TradeTracker()
    round_trip(tracker)
    feed(tracker, undock(30), dock(40, DEPOT), sell(41, DEPOT, PAINITE, 1, 300_000, paid=0))
    assert stats_of(tracker).flight_time == timedelta(minutes=20)


def test_ejected_goods_are_a_loss_at_the_price_paid() -> None:
    tracker = TradeTracker()
    feed(tracker, dock(0, AMANO), buy(1, AMANO, PALLADIUM, 100, 5_000), undock(2))
    [updated] = tracker.handle(CargoEjected(at(3), PALLADIUM, 10))
    assert isinstance(updated, TradeUpdated)
    assert updated.stats.losses == 50_000
    assert updated.stats.profit == -50_000
    assert updated.stats.cargo == GoodsTally(90, 450_000)


def test_ejecting_goods_of_unknown_cost_is_no_loss() -> None:
    tracker = TradeTracker()
    feed(tracker, dock(0, AMANO), buy(1, AMANO, PALLADIUM, 100, 5_000))
    assert tracker.handle(CargoEjected(at(3), PAINITE, 10)) == []


def test_ejecting_without_a_session_is_no_loss() -> None:
    tracker = TradeTracker()
    feed(tracker, dock(0, AMANO), buy(1, AMANO, PALLADIUM, 100, 5_000))
    tracker.reset(at(2))
    assert tracker.handle(CargoEjected(at(3), PALLADIUM, 10)) == []


def test_death_loses_the_cargo_and_ends_the_session() -> None:
    tracker = TradeTracker()
    round_trip(tracker)
    feed(tracker, buy(27, VERNE, CMM, 100, 5_000), undock(30))
    notifications = tracker.handle(CommanderDied(at(35)))
    assert isinstance(notifications[0], TradeUpdated)
    ended = notifications[-1]
    assert isinstance(ended, TradeEnded)
    assert (ended.at, ended.reason) == (at(35), TradeEndReason.DIED)
    assert ended.stats.losses == 500_000
    assert ended.stats.profit == 4_000_000
    assert ended.stats.cargo == GoodsTally()
    # The leg ends with the ship: nothing more is in flight
    assert ended.stats.flight_time == timedelta(minutes=20)
    assert tracker.session is None


def test_death_without_cargo_ends_the_session_only() -> None:
    tracker = TradeTracker()
    round_trip(tracker)
    [ended] = tracker.handle(CommanderDied(at(40)))
    assert isinstance(ended, TradeEnded)
    assert ended.stats.losses == 0


def test_death_without_a_session_forgets_the_cargo() -> None:
    tracker = TradeTracker()
    feed(tracker, dock(0, AMANO), buy(1, AMANO, PALLADIUM, 100, 5_000))
    tracker.reset(at(2))
    assert tracker.handle(CommanderDied(at(3))) == []
    feed(tracker, buy(4, AMANO, CMM, 1, 1_000))
    assert stats_of(tracker).cargo == GoodsTally(1, 1_000)


def test_game_closed_ends_the_session_and_keeps_the_cargo() -> None:
    tracker = TradeTracker()
    feed(tracker, dock(0, AMANO), buy(1, AMANO, PALLADIUM, 100, 5_000))
    [ended] = tracker.handle(GameClosed(at(10)))
    assert isinstance(ended, TradeEnded)
    assert ended.reason is TradeEndReason.GAME_CLOSED
    assert tracker.handle(GameClosed(at(11))) == []
    feed(tracker, GameLoaded(at(20), AMANO), sell(21, AMANO, PALLADIUM, 100, 5_500, paid=5_000))
    [route] = stats_of(tracker).routes
    assert route.origin == AMANO


def test_reset_ends_the_session() -> None:
    tracker = TradeTracker()
    round_trip(tracker)
    ended = tracker.reset(at(30))
    assert ended is not None
    assert (ended.reason, ended.stats.profit) == (TradeEndReason.MANUAL, 4_500_000)
    assert tracker.reset(at(31)) is None


def test_a_new_session_does_not_count_the_flight_before_it() -> None:
    tracker = TradeTracker()
    round_trip(tracker)
    tracker.reset(at(30))
    feed(tracker, undock(31), dock(50, AMANO), buy(51, AMANO, PALLADIUM, 10, 5_000))
    assert stats_of(tracker).flight_time == timedelta(0)


def test_game_loaded_in_flight_starts_the_leg() -> None:
    tracker = TradeTracker()
    feed(tracker, dock(0, AMANO), buy(1, AMANO, PALLADIUM, 10, 5_000))
    feed(
        tracker,
        GameLoaded(at(10), None),
        dock(20, VERNE),
        sell(21, VERNE, PALLADIUM, 10, 9_000, paid=5_000),
    )
    assert stats_of(tracker).flight_time == timedelta(minutes=10)


def test_game_loaded_docked_names_the_market() -> None:
    tracker = TradeTracker()
    feed(tracker, GameLoaded(at(0), VERNE), sell(1, VERNE, PALLADIUM, 10, 9_000, paid=5_000))
    assert stats_of(tracker).routes[0].destination.station == "Verne Venture"


def test_cargo_inventory_never_holds_more_than_on_board() -> None:
    tracker = TradeTracker()
    feed(
        tracker,
        dock(0, AMANO),
        buy(1, AMANO, PALLADIUM, 100, 5_000),
        buy(1, AMANO, CMM, 10, 1_000),
    )
    # Twenty tons went to a mission, the CMM to a fleet carrier
    assert tracker.handle(CargoInventory(at(2), ((PALLADIUM, 80),))) == []
    assert stats_of(tracker).cargo == GoodsTally(80, 400_000)
    # More on board than seen bought: bought before EDMC started, cost unknown
    tracker.handle(CargoInventory(at(3), ((PALLADIUM, 200),)))
    assert stats_of(tracker).cargo == GoodsTally(80, 400_000)


def test_the_route_keeps_the_name_the_purchase_gave() -> None:
    tracker = TradeTracker()
    named = Commodity("cmmcomposite", "Composite MMC")
    feed(
        tracker,
        buy(1, VERNE, CMM, 10, 5_000),
        buy(2, VERNE, named, 10, 5_000),
        sell(3, AMANO, CMM, 20, 20_000, paid=5_000),
    )
    [route] = stats_of(tracker).routes
    assert route.commodity.display_name == "Composite MMC"


CARRIER = Market(9, "TZF-66Z", fleet_carrier=True)
GOLD = Commodity("gold")


def transfer(minutes: float, *moves: tuple[Commodity, int, TransferDirection]) -> CargoTransferred:
    return CargoTransferred(
        at(minutes), tuple(Transfer(commodity, count, way) for commodity, count, way in moves)
    )


def deposit(minutes: float, commodity: Commodity, count: int) -> CargoTransferred:
    return transfer(minutes, (commodity, count, TransferDirection.TO_CARRIER))


def withdraw(minutes: float, commodity: Commodity, count: int) -> CargoTransferred:
    return transfer(minutes, (commodity, count, TransferDirection.TO_SHIP))


def haul_gold(tracker: TradeTracker) -> list[TradeNotification]:
    """Gold bought at Tan Depot, 10 minutes of flight, deposited at the carrier."""
    return feed(
        tracker,
        dock(0, DEPOT),
        buy(1, DEPOT, GOLD, 100, 5_000),
        undock(2),
        dock(12, CARRIER),
        deposit(13, GOLD, 100),
    )


def test_a_deposit_is_counted_with_its_transfers() -> None:
    tracker = TradeTracker()
    haul_gold(tracker)
    notifications = feed(tracker, buy(14, CARRIER, GOLD, 1, 5_000), deposit(15, GOLD, 1))
    assert isinstance(notifications[-1], TradeUpdated)
    stats = stats_of(tracker)
    assert stats.transfers == (TransferStats(GOLD, TransferKind.DEPOSIT, 101, 2),)
    assert stats.cargo == GoodsTally()
    assert (stats.profit, stats.tons_sold) == (0, 0)


def test_the_leg_before_a_deposit_counts() -> None:
    tracker = TradeTracker()
    haul_gold(tracker)
    assert stats_of(tracker).flight_time == timedelta(minutes=10)


def test_a_transfer_starts_the_session() -> None:
    tracker = TradeTracker()
    notifications = feed(tracker, dock(0, CARRIER), withdraw(1, GOLD, 50))
    assert isinstance(notifications[0], TradeStarted)
    assert stats_of(tracker).transfers == (TransferStats(GOLD, TransferKind.WITHDRAWAL, 50, 1),)


def test_deposited_goods_are_not_lost_with_the_ship() -> None:
    tracker = TradeTracker()
    haul_gold(tracker)
    feed(tracker, undock(14))
    ended = tracker.handle(CommanderDied(at(20)))[-1]
    assert isinstance(ended, TradeEnded)
    assert ended.stats.losses == 0


def test_a_withdrawal_brings_back_the_cost_and_the_origin() -> None:
    tracker = TradeTracker()
    haul_gold(tracker)
    feed(tracker, withdraw(30, GOLD, 40), undock(31), dock(41, VERNE))
    assert stats_of(tracker).cargo == GoodsTally(40, 200_000)
    feed(tracker, sell(42, VERNE, GOLD, 40, 9_000, paid=5_000))
    [route] = stats_of(tracker).routes
    assert route.origin == DEPOT
    assert stats_of(tracker).flight_time == timedelta(minutes=20)


def test_goods_of_unknown_cost_move_without_cost() -> None:
    tracker = TradeTracker()
    feed(tracker, dock(0, CARRIER), withdraw(1, GOLD, 50))
    assert stats_of(tracker).cargo == GoodsTally()
    feed(tracker, buy(2, CARRIER, GOLD, 10, 5_000), deposit(3, GOLD, 60))
    feed(tracker, withdraw(4, GOLD, 60))
    # Only the ten tons bought are known: they come back at their cost
    assert stats_of(tracker).cargo == GoodsTally(10, 50_000)


def test_transfers_with_an_srv_are_ignored() -> None:
    tracker = TradeTracker()
    feed(tracker, dock(0, AMANO), buy(1, AMANO, GOLD, 10, 5_000), undock(2))
    assert tracker.handle(transfer(3, (GOLD, 4, TransferDirection.TO_SRV))) == []
    # Back from the SRV: not docked at a carrier
    assert tracker.handle(withdraw(4, GOLD, 4)) == []
    feed(tracker, dock(10, VERNE))
    assert tracker.handle(withdraw(11, GOLD, 4)) == []  # docked, but not at a carrier
    assert stats_of(tracker).transfers == ()


def test_a_deposit_away_from_a_known_carrier_is_still_a_deposit() -> None:
    tracker = TradeTracker()
    feed(tracker, buy(1, AMANO, GOLD, 10, 5_000), deposit(2, GOLD, 10))
    stats = stats_of(tracker)
    assert stats.transfers == (TransferStats(GOLD, TransferKind.DEPOSIT, 10, 1),)
    assert stats.cargo == GoodsTally()


def test_one_transfer_entry_may_move_several_commodities() -> None:
    tracker = TradeTracker()
    feed(
        tracker,
        dock(0, CARRIER),
        transfer(
            1,
            (GOLD, 10, TransferDirection.TO_CARRIER),
            (CMM, 5, TransferDirection.TO_CARRIER),
            (PALLADIUM, 3, TransferDirection.TO_SHIP),
        ),
    )
    assert stats_of(tracker).transfers == (
        TransferStats(GOLD, TransferKind.DEPOSIT, 10, 1),
        TransferStats(CMM, TransferKind.DEPOSIT, 5, 1),
        TransferStats(PALLADIUM, TransferKind.WITHDRAWAL, 3, 1),
    )
