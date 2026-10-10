"""The on-foot part of the engineering tracker (ADR 0027)."""

from datetime import UTC, datetime, timedelta

from edrockmaster.domain.engineering.catalogue import OnFootKind
from edrockmaster.domain.engineering.journal import CommanderDied, GameClosed
from edrockmaster.domain.engineering.on_foot import CarrierMove, OnFootHolding
from edrockmaster.domain.engineering.on_foot_journal import (
    BackpackChanged,
    BackpackStated,
    Boarded,
    CarrierKnown,
    DockedAt,
    EquipmentSold,
    LoadoutChosen,
    LockerStated,
    Stock,
    Suit,
    SuitBought,
    Undocked,
    Weapon,
    WeaponBought,
    WeaponEquipped,
)
from edrockmaster.domain.engineering.session import (
    CollectionEnded,
    CollectionStarted,
    EngineeringNotification,
    EngineeringTracker,
    EngineeringUpdated,
)
from tests.domain.engineering.catalogue_data import catalogue

T0 = datetime(2026, 10, 5, 21, 0, tzinfo=UTC)
ITEM, COMPONENT, DATA, CONSUMABLE = (
    OnFootKind.ITEM,
    OnFootKind.COMPONENT,
    OnFootKind.DATA,
    OnFootKind.CONSUMABLE,
)


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def locker(*stock: Stock, minutes: int = 0) -> LockerStated:
    return LockerStated(at(minutes), stock)


def added(*stock: Stock, minutes: int = 1) -> BackpackChanged:
    return BackpackChanged(at(minutes), stock, ())


def removed(*stock: Stock, minutes: int = 1) -> BackpackChanged:
    return BackpackChanged(at(minutes), (), stock)


def updates(notifications: list[EngineeringNotification]) -> list[EngineeringUpdated]:
    return [n for n in notifications if isinstance(n, EngineeringUpdated)]


def holdings(tracker: EngineeringTracker) -> dict[str, tuple[int, int, int]]:
    """(locker, backpack, mission) of each material held."""
    inventory = tracker.on_foot_inventory
    assert inventory is not None
    return {h.symbol: (h.locker, h.backpack, h.mission) for h in inventory}


def test_the_on_foot_inventory_is_unknown_until_the_game_states_the_locker() -> None:
    tracker = EngineeringTracker(catalogue())
    assert tracker.on_foot_inventory is None
    assert not tracker.stats().on_foot_known
    notifications = tracker.handle(locker(Stock("graphene", COMPONENT, 4, "Graphène")))
    assert [u.progressed for u in updates(notifications)] == [False]
    assert tracker.stats().on_foot_known
    assert tracker.on_foot_inventory == (
        OnFootHolding("graphene", COMPONENT, locker=4, backpack=0, mission=0),
    )
    assert tracker.name_of("graphene") == "Graphène"


def test_the_inventory_is_the_last_locker_plus_the_backpack() -> None:
    tracker = EngineeringTracker(catalogue())
    tracker.handle(locker(Stock("graphene", COMPONENT, 4), Stock("chemicalsample", ITEM, 2)))
    tracker.handle(BackpackStated(at(1), (Stock("graphene", COMPONENT, 1),)))
    # Each statement replaces the whole place
    tracker.handle(locker(Stock("graphene", COMPONENT, 5), minutes=2))
    assert holdings(tracker) == {"graphene": (5, 1, 0)}


def test_mission_items_are_apart_and_consumables_are_shown() -> None:
    tracker = EngineeringTracker(catalogue())
    tracker.handle(
        locker(
            Stock("gmeds", ITEM, 3),
            Stock("gmeds", ITEM, 1, mission=True),
            Stock("healthpack", CONSUMABLE, 99),
        )
    )
    assert holdings(tracker) == {"gmeds": (3, 0, 1), "healthpack": (99, 0, 0)}
    # What counts towards goals: the player's own, no consumable
    assert tracker.on_foot_held() == {"gmeds": 3}


def test_materials_picked_up_start_a_collection_and_are_counted_by_kind() -> None:
    tracker = EngineeringTracker(catalogue())
    tracker.handle(locker())
    notifications = tracker.handle(
        added(Stock("ionbattery", COMPONENT, 1), Stock("factionnews", DATA, 2))
    )
    assert notifications[0] == CollectionStarted(at(1))
    assert [u.progressed for u in updates(notifications)] == [True]
    tracker.handle(added(Stock("chemicalsample", ITEM, 1), minutes=2))
    collection = tracker.stats().collection
    assert collection is not None
    assert collection.gained_on_foot == {COMPONENT: 1, DATA: 2, ITEM: 1}
    assert holdings(tracker)["factionnews"] == (0, 2, 0)


def test_consumables_and_mission_items_are_no_collection() -> None:
    tracker = EngineeringTracker(catalogue())
    tracker.handle(locker())
    notifications = tracker.handle(
        added(Stock("energycell", CONSUMABLE, 1), Stock("gmeds", ITEM, 1, mission=True))
    )
    assert not any(isinstance(n, CollectionStarted) for n in notifications)
    assert [u.progressed for u in updates(notifications)] == [False]
    assert tracker.stats().collection is None
    assert holdings(tracker) == {"energycell": (0, 1, 0), "gmeds": (0, 0, 1)}


def test_what_leaves_the_backpack_is_taken_off_it() -> None:
    tracker = EngineeringTracker(catalogue())
    tracker.handle(locker())
    tracker.handle(added(Stock("gmeds", ITEM, 2)))
    tracker.handle(removed(Stock("gmeds", ITEM, 1), Stock("healthpack", CONSUMABLE, 1)))
    assert holdings(tracker) == {"gmeds": (0, 1, 0)}


def test_boarding_moves_the_backpack_to_the_locker_until_the_game_restates_it() -> None:
    tracker = EngineeringTracker(catalogue())
    tracker.handle(locker(Stock("gmeds", ITEM, 1)))
    tracker.handle(added(Stock("gmeds", ITEM, 2), Stock("graphene", COMPONENT, 1)))
    tracker.handle(Boarded(at(2)))
    assert holdings(tracker) == {"gmeds": (3, 0, 0), "graphene": (1, 0, 0)}
    # The game's own statement, a second later, is the truth
    tracker.handle(locker(Stock("gmeds", ITEM, 3), Stock("graphene", COMPONENT, 1), minutes=3))
    assert holdings(tracker) == {"gmeds": (3, 0, 0), "graphene": (1, 0, 0)}


def test_a_death_loses_what_the_backpack_carried() -> None:
    tracker = EngineeringTracker(catalogue())
    tracker.handle(locker(Stock("gmeds", ITEM, 1)))
    tracker.handle(
        added(
            Stock("gmeds", ITEM, 2),
            Stock("energycell", CONSUMABLE, 1),
            Stock("insight", ITEM, 1, mission=True),
        )
    )
    notifications = tracker.handle(CommanderDied(at(5)))
    assert [u.progressed for u in updates(notifications)] == [True]
    collection = tracker.stats().collection
    assert collection is not None
    assert collection.lost_on_foot == 2  # the player's own materials only
    assert holdings(tracker) == {"gmeds": (1, 0, 0)}


def test_a_death_with_an_empty_backpack_changes_nothing() -> None:
    tracker = EngineeringTracker(catalogue())
    tracker.handle(locker(Stock("gmeds", ITEM, 1)))
    assert updates(tracker.handle(CommanderDied(at(5))))[0].progressed is False
    assert tracker.stats().collection is None


def test_the_collection_ends_with_the_game() -> None:
    tracker = EngineeringTracker(catalogue())
    tracker.handle(locker())
    tracker.handle(added(Stock("gmeds", ITEM, 1)))
    notifications = tracker.handle(GameClosed(at(9)))
    assert isinstance(notifications[0], CollectionEnded)
    assert tracker.stats().collection is None


SUIT = Suit(1701757244975121, "tacticalsuit", 3, ())
TORMENTOR = Weapon(1700319560391861, "wpn_s_pistol_plasma_charged", 1, ())
ECLIPSE = Weapon(1878319875493998, "wpn_m_submachinegun_laser_fauto", 3, ("weapon_handling",))


def test_the_equipment_seen_in_the_journal() -> None:
    tracker = EngineeringTracker(catalogue())
    tracker.handle(LoadoutChosen(at(0), SUIT, (TORMENTOR,)))
    tracker.handle(WeaponBought(at(1), ECLIPSE))
    tracker.handle(SuitBought(at(2), Suit(1878178949341729, "utilitysuit", 2, ())))
    assert set(tracker.equipment) == {SUIT.id, TORMENTOR.id, ECLIPSE.id, 1878178949341729}
    # A later statement of the same piece replaces it: a class or a modification gained
    better = Weapon(TORMENTOR.id, TORMENTOR.symbol, 2, ("weapon_stability",))
    tracker.handle(WeaponEquipped(at(3), better))
    assert tracker.equipment[TORMENTOR.id] == better
    tracker.handle(EquipmentSold(at(4), ECLIPSE.id))
    assert ECLIPSE.id not in tracker.equipment


CARRIER = 3711717120


def docked_at_the_carrier(tracker: EngineeringTracker) -> None:
    tracker.handle(CarrierKnown(at(0), CARRIER))
    tracker.handle(locker(Stock("gmeds", ITEM, 4), Stock("graphene", COMPONENT, 2)))
    tracker.handle(DockedAt(at(1), CARRIER))


def test_what_leaves_the_locker_at_the_player_s_carrier_is_a_move_counted_nowhere() -> None:
    tracker = EngineeringTracker(catalogue())
    docked_at_the_carrier(tracker)
    tracker.handle(
        locker(Stock("graphene", COMPONENT, 2), Stock("healthpack", CONSUMABLE, 9), minutes=3)
    )
    tracker.handle(locker(minutes=4))
    assert tracker.carrier_moves == (CarrierMove(at(1), at(4), {"gmeds": -4, "graphene": -2}),)
    assert tracker.on_foot_held() == {}


def test_what_comes_back_from_the_carrier_is_a_move_too() -> None:
    tracker = EngineeringTracker(catalogue())
    docked_at_the_carrier(tracker)
    tracker.handle(locker(Stock("gmeds", ITEM, 6), Stock("graphene", COMPONENT, 2), minutes=3))
    tracker.handle(Undocked(at(5)))
    # Undocked: a change of the locker elsewhere is no move
    tracker.handle(locker(Stock("graphene", COMPONENT, 2), minutes=6))
    assert tracker.carrier_moves == (CarrierMove(at(1), at(3), {"gmeds": 2}),)


def test_the_backpack_brought_aboard_at_the_carrier_is_no_move() -> None:
    tracker = EngineeringTracker(catalogue())
    docked_at_the_carrier(tracker)
    tracker.handle(added(Stock("ionbattery", COMPONENT, 1), minutes=2))
    tracker.handle(Boarded(at(3)))
    tracker.handle(
        locker(
            Stock("gmeds", ITEM, 4),
            Stock("graphene", COMPONENT, 2),
            Stock("ionbattery", COMPONENT, 1),
            minutes=4,
        )
    )
    assert tracker.carrier_moves == ()


def test_another_carrier_or_an_unknown_one_is_no_move() -> None:
    tracker = EngineeringTracker(catalogue())
    tracker.handle(locker(Stock("gmeds", ITEM, 4)))
    tracker.handle(DockedAt(at(1), CARRIER))  # the player's carrier is not known
    tracker.handle(locker(minutes=2))
    tracker.handle(CarrierKnown(at(3), CARRIER + 1))
    tracker.handle(locker(Stock("gmeds", ITEM, 1), minutes=4))
    assert tracker.carrier_moves == ()


def test_each_docking_is_its_own_move() -> None:
    tracker = EngineeringTracker(catalogue())
    docked_at_the_carrier(tracker)
    tracker.handle(locker(Stock("graphene", COMPONENT, 2), minutes=2))
    tracker.handle(Undocked(at(3)))
    tracker.handle(DockedAt(at(10), CARRIER))
    tracker.handle(locker(Stock("graphene", COMPONENT, 2), Stock("gmeds", ITEM, 1), minutes=11))
    assert tracker.carrier_moves == (
        CarrierMove(at(1), at(2), {"gmeds": -4}),
        CarrierMove(at(10), at(11), {"gmeds": 1}),
    )
