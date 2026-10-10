"""Translation of the on-foot journal entries into facts of the engineering domain (ADR 0027).

What the player's journals show (survey of 30 September to 10 October 2026):

- ``ShipLocker`` states the whole ship locker at load, after each jump, entry
  and exit of supercruise, craft or boarding; an entry without content only
  points to ``ShipLocker.json``, which then holds the content of the last full
  one, so it is ignored. ``Backpack`` states the whole backpack (empty at each
  disembarking); ``BackpackChange`` gives each change, with each material's kind.
- Boarding a ship or an SRV (``Embark``) writes no transfer: the next
  ``ShipLocker`` holds what the backpack carried.
- ``SuitLoadout``, ``SwitchSuitLoadout`` and ``CreateSuitLoadout`` give the suit
  and weapons of a loadout, with their class and modifications;
  ``LoadoutEquipModule``, ``BuySuit``, ``BuyWeapon``, ``SellSuit`` and
  ``SellWeapon`` one piece of equipment. The class of a suit is in its name
  (``tacticalsuit_class3``); the flight suit has none.

- The player's own fleet carrier: ``CarrierLocation`` (at load, for its owner)
  and ``CarrierStats`` give its id; ``Docked`` the ``MarketID`` of where the ship
  docked, the carrier's id at a carrier (ADR 0029). A move of on-foot materials
  to or from the carrier writes no event.

``CollectItems``, ``DropItems`` and ``UseConsumable`` are not read: the backpack's
own events tell the same, and data downloads only show there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from edrockmaster.domain.engineering.catalogue import OnFootKind
from edrockmaster.domain.journal_reading import (
    Entry,
    MalformedEntryError,
    Parser,
    items,
    optional,
    required,
)

_SECTIONS = {
    "Items": OnFootKind.ITEM,
    "Components": OnFootKind.COMPONENT,
    "Data": OnFootKind.DATA,
    "Consumables": OnFootKind.CONSUMABLE,
}
_TYPES = {
    "Item": OnFootKind.ITEM,
    "Component": OnFootKind.COMPONENT,
    "Data": OnFootKind.DATA,
    "Consumable": OnFootKind.CONSUMABLE,
}
_SUIT_CLASS = re.compile(r"^(?P<suit>.+)_class(?P<class>[1-5])$")
_CLASSES = range(1, 6)


@dataclass(frozen=True, slots=True)
class Stock:
    """A count of one on-foot material, in the locker, the backpack or a change of it."""

    symbol: str
    """As the journal writes it, in lower case (``chemicalsample``)."""
    kind: OnFootKind
    count: int
    name: str | None = None
    """In the game's language, when the journal gives it."""
    mission: bool = False
    """Held for a mission (``MissionID``): not the player's. An ``OwnerID`` other than 0 is
    the owner a stolen item was taken from: the item is the player's all the same."""


@dataclass(frozen=True, slots=True)
class LockerStated:
    at: datetime
    stock: tuple[Stock, ...]


@dataclass(frozen=True, slots=True)
class BackpackStated:
    at: datetime
    stock: tuple[Stock, ...]


@dataclass(frozen=True, slots=True)
class BackpackChanged:
    at: datetime
    added: tuple[Stock, ...]
    removed: tuple[Stock, ...]


@dataclass(frozen=True, slots=True)
class Boarded:
    """The commander boarded a ship, an SRV or a taxi: the backpack goes to the locker."""

    at: datetime


@dataclass(frozen=True, slots=True)
class Suit:
    id: int
    symbol: str
    """Its type, without its class, in lower case (``tacticalsuit``)."""
    suit_class: int | None
    """1 to 5; ``None`` for the flight suit, which has none."""
    mods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Weapon:
    id: int
    symbol: str
    """Its type, in lower case (``wpn_m_submachinegun_laser_fauto``)."""
    weapon_class: int
    mods: tuple[str, ...]
    name: str | None = None
    """In the game's language, when the journal gives it."""


@dataclass(frozen=True, slots=True)
class LoadoutChosen:
    """A loadout worn, switched to or created: its suit and weapons."""

    at: datetime
    suit: Suit
    weapons: tuple[Weapon, ...]


@dataclass(frozen=True, slots=True)
class WeaponEquipped:
    at: datetime
    weapon: Weapon


@dataclass(frozen=True, slots=True)
class SuitBought:
    at: datetime
    suit: Suit


@dataclass(frozen=True, slots=True)
class WeaponBought:
    at: datetime
    weapon: Weapon


@dataclass(frozen=True, slots=True)
class EquipmentSold:
    at: datetime
    id: int


@dataclass(frozen=True, slots=True)
class CarrierKnown:
    """The player's own fleet carrier."""

    at: datetime
    carrier_id: int


@dataclass(frozen=True, slots=True)
class DockedAt:
    at: datetime
    market_id: int
    """The carrier's id, when docked at a carrier."""


@dataclass(frozen=True, slots=True)
class Undocked:
    at: datetime


type OnFootFact = (
    LockerStated
    | BackpackStated
    | BackpackChanged
    | Boarded
    | LoadoutChosen
    | WeaponEquipped
    | SuitBought
    | WeaponBought
    | EquipmentSold
    | CarrierKnown
    | DockedAt
    | Undocked
)


def _stock(entry: Entry, kind: OnFootKind) -> Stock:
    symbol = required(entry, "Name", str).strip().lower()
    count = required(entry, "Count", int)
    if not symbol:
        raise MalformedEntryError("Name")
    if count < 0:
        raise MalformedEntryError("Count")
    return Stock(symbol, kind, count, optional(entry, "Name_Localised", str), "MissionID" in entry)


def _typed(entry: Entry) -> Stock:
    kind = _TYPES.get(required(entry, "Type", str))
    if kind is None:
        raise MalformedEntryError("Type")
    return _stock(entry, kind)


def _content(entry: Entry) -> tuple[Stock, ...]:
    return tuple(
        _stock(item, kind)
        for section, kind in _SECTIONS.items()
        for item in (items(entry, section) if section in entry else [])
    )


def _locker(entry: Entry, at: datetime) -> LockerStated | None:
    if not any(section in entry for section in _SECTIONS):
        return None
    return LockerStated(at, _content(entry))


def _backpack(entry: Entry, at: datetime) -> BackpackStated:
    return BackpackStated(at, _content(entry))


def _backpack_change(entry: Entry, at: datetime) -> BackpackChanged:
    def listed(name: str) -> tuple[Stock, ...]:
        return tuple(_typed(item) for item in (items(entry, name) if name in entry else []))

    return BackpackChanged(at, listed("Added"), listed("Removed"))


def _boarded(_entry: Entry, at: datetime) -> Boarded:
    return Boarded(at)


def _mods(entry: Entry, name: str) -> tuple[str, ...]:
    mods = required(entry, name, list)
    if not all(isinstance(mod, str) for mod in mods):
        raise MalformedEntryError(name)
    return tuple(mod.strip().lower() for mod in mods)


def _suit(entry: Entry, id_name: str, symbol_name: str) -> Suit:
    symbol = required(entry, symbol_name, str).strip().lower()
    match = _SUIT_CLASS.match(symbol)
    return Suit(
        required(entry, id_name, int),
        match["suit"] if match else symbol,
        int(match["class"]) if match else None,
        _mods(entry, "SuitMods") if "SuitMods" in entry else (),
    )


def _weapon(entry: Entry, symbol_name: str) -> Weapon:
    weapon_class = required(entry, "Class", int)
    if weapon_class not in _CLASSES:
        raise MalformedEntryError("Class")
    return Weapon(
        required(entry, "SuitModuleID", int),
        required(entry, symbol_name, str).strip().lower(),
        weapon_class,
        _mods(entry, "WeaponMods") if "WeaponMods" in entry else (),
        optional(entry, f"{symbol_name}_Localised", str),
    )


def _loadout(entry: Entry, at: datetime) -> LoadoutChosen:
    return LoadoutChosen(
        at,
        _suit(entry, "SuitID", "SuitName"),
        tuple(_weapon(module, "ModuleName") for module in items(entry, "Modules")),
    )


def _equipped(entry: Entry, at: datetime) -> WeaponEquipped:
    return WeaponEquipped(at, _weapon(entry, "ModuleName"))


def _suit_bought(entry: Entry, at: datetime) -> SuitBought:
    return SuitBought(at, _suit(entry, "SuitID", "Name"))


def _weapon_bought(entry: Entry, at: datetime) -> WeaponBought:
    return WeaponBought(at, _weapon(entry, "Name"))


def _suit_sold(entry: Entry, at: datetime) -> EquipmentSold:
    return EquipmentSold(at, required(entry, "SuitID", int))


def _weapon_sold(entry: Entry, at: datetime) -> EquipmentSold:
    return EquipmentSold(at, required(entry, "SuitModuleID", int))


def _carrier(entry: Entry, at: datetime) -> CarrierKnown | None:
    # Older lines have no CarrierType; a squadron's carrier is not the player's own
    if optional(entry, "CarrierType", str) not in (None, "FleetCarrier"):
        return None
    return CarrierKnown(at, required(entry, "CarrierID", int))


def _docked(entry: Entry, at: datetime) -> DockedAt:
    return DockedAt(at, required(entry, "MarketID", int))


def _undocked(_entry: Entry, at: datetime) -> Undocked:
    return Undocked(at)


ON_FOOT_PARSERS: dict[str, Parser[OnFootFact | None]] = {
    "ShipLocker": _locker,
    "Backpack": _backpack,
    "BackpackChange": _backpack_change,
    "Embark": _boarded,
    "SuitLoadout": _loadout,
    "SwitchSuitLoadout": _loadout,
    "CreateSuitLoadout": _loadout,
    "LoadoutEquipModule": _equipped,
    "BuySuit": _suit_bought,
    "BuyWeapon": _weapon_bought,
    "SellSuit": _suit_sold,
    "SellWeapon": _weapon_sold,
    "CarrierLocation": _carrier,
    "CarrierStats": _carrier,
    "Docked": _docked,
    "Undocked": _undocked,
}
