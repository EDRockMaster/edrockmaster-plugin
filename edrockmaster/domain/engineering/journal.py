"""Translation of raw journal entries into facts of the engineering domain (ADR 0017).

The engineering context's anti-corruption layer for the game journal, built on
the tolerant helpers of the shared kernel (``journal_reading``). Ship materials
only: Odyssey's on-foot materials have their own events, for a later ADR.

Materials are named by their journal symbol in lower case (``chemicalmanipulators``);
the catalogue gives their category and grade, so the categories the journal
writes (sometimes as ``$MICRORESOURCE_CATEGORY_Raw;``) are not read.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from edrockmaster.domain.journal_reading import (
    Entry,
    MalformedEntryError,
    Parser,
    items,
    optional,
    required,
    translate,
)

_INVENTORY_CATEGORIES = ("Raw", "Manufactured", "Encoded")


@dataclass(frozen=True, slots=True)
class MaterialChange:
    """``count`` more (or fewer, when negative) of a material."""

    symbol: str
    count: int
    name: str | None = None
    """In the game's language, when the journal gives it."""


class ChangeCause(Enum):
    COLLECTED = "collected"
    REWARDED = "rewarded"
    """A mission reward."""
    DISCARDED = "discarded"
    TRADED = "traded"
    """At a material trader: one material paid, another received."""
    SYNTHESISED = "synthesised"
    BROKER = "broker"
    """Spent at a technology broker."""
    CONTRIBUTED = "contributed"
    """Given to an engineer, to unlock them."""
    RESEARCH = "research"
    """Given to a scientific research effort."""
    ENGINEERED = "engineered"
    """Spent on a roll of a blueprint or an experimental effect."""


@dataclass(frozen=True, slots=True)
class MaterialsChanged:
    at: datetime
    cause: ChangeCause
    changes: tuple[MaterialChange, ...]


@dataclass(frozen=True, slots=True)
class InventoryStated:
    """The whole inventory, as the game states it when it loads (``Materials``)."""

    at: datetime
    counts: tuple[MaterialChange, ...]
    """One entry per material held: its count, and its name in the game's language."""


@dataclass(frozen=True, slots=True)
class BlueprintApplied:
    """An engineer applied a roll of a blueprint, or an experimental effect (``EngineerCraft``)."""

    at: datetime
    blueprint: str
    grade: int
    module_item: str
    """The item engineered, as the journal names it (``int_powerdistributor_size7_class5``)."""
    engineer_id: int | None
    effect: str | None
    """The experimental effect applied, if this was one; the blueprint is then the module's."""
    spent: tuple[MaterialChange, ...]


class EngineerStatus(Enum):
    KNOWN = "Known"
    INVITED = "Invited"
    ACQUAINTED = "Acquainted"
    UNLOCKED = "Unlocked"
    BARRED = "Barred"


@dataclass(frozen=True, slots=True)
class EngineerState:
    engineer_id: int
    name: str
    status: EngineerStatus
    rank: int | None = None
    """1 to 5 once unlocked."""


@dataclass(frozen=True, slots=True)
class EngineersStated:
    """Every engineer, as the game states them when it loads."""

    at: datetime
    engineers: tuple[EngineerState, ...]


@dataclass(frozen=True, slots=True)
class EngineerProgressed:
    at: datetime
    engineer: EngineerState


@dataclass(frozen=True, slots=True)
class GameClosed:
    at: datetime


type Fact = (
    MaterialsChanged
    | InventoryStated
    | BlueprintApplied
    | EngineersStated
    | EngineerProgressed
    | GameClosed
)


def parse_entry(entry: Entry) -> Fact | None:
    """Translate one journal entry; ``None`` if irrelevant to engineering or malformed."""
    return translate(entry, _PARSERS)


def _symbol(entry: Entry, name: str) -> str:
    symbol = required(entry, name, str).strip().lower()
    if not symbol:
        raise MalformedEntryError(name)
    return symbol


def _count(entry: Entry, name: str) -> int:
    count = required(entry, name, int)
    if count < 0:
        raise MalformedEntryError(name)
    return count


def _change(entry: Entry, sign: int, symbol: str = "Name", count: str = "Count") -> MaterialChange:
    return MaterialChange(
        _symbol(entry, symbol),
        sign * _count(entry, count),
        optional(entry, f"{symbol}_Localised", str),
    )


def _inventory(entry: Entry, at: datetime) -> InventoryStated:
    counts = tuple(
        _change(item, 1)
        for category in _INVENTORY_CATEGORIES
        for item in (items(entry, category) if category in entry else [])
    )
    return InventoryStated(at, counts)


def _collected(entry: Entry, at: datetime) -> MaterialsChanged:
    return MaterialsChanged(at, ChangeCause.COLLECTED, (_change(entry, 1),))


def _discarded(entry: Entry, at: datetime) -> MaterialsChanged:
    return MaterialsChanged(at, ChangeCause.DISCARDED, (_change(entry, -1),))


def _traded(entry: Entry, at: datetime) -> MaterialsChanged:
    paid = required(entry, "Paid", dict)
    received = required(entry, "Received", dict)
    return MaterialsChanged(
        at,
        ChangeCause.TRADED,
        (
            _change(paid, -1, "Material", "Quantity"),
            _change(received, 1, "Material", "Quantity"),
        ),
    )


def _spent(entry: Entry, name: str) -> tuple[MaterialChange, ...]:
    return tuple(_change(item, -1) for item in items(entry, name))


def _synthesised(entry: Entry, at: datetime) -> MaterialsChanged:
    return MaterialsChanged(at, ChangeCause.SYNTHESISED, _spent(entry, "Materials"))


def _broker(entry: Entry, at: datetime) -> MaterialsChanged | None:
    if "Materials" not in entry:
        return None
    return MaterialsChanged(at, ChangeCause.BROKER, _spent(entry, "Materials"))


def _contributed(entry: Entry, at: datetime) -> MaterialsChanged | None:
    if required(entry, "Type", str) != "Materials":
        return None  # commodities, bounties, bonds…
    return MaterialsChanged(
        at, ChangeCause.CONTRIBUTED, (_change(entry, -1, "Material", "Quantity"),)
    )


def _research(entry: Entry, at: datetime) -> MaterialsChanged:
    return MaterialsChanged(at, ChangeCause.RESEARCH, (_change(entry, -1),))


def _rewarded(entry: Entry, at: datetime) -> MaterialsChanged | None:
    if "MaterialsReward" not in entry:
        return None
    rewards = tuple(_change(item, 1) for item in items(entry, "MaterialsReward"))
    return MaterialsChanged(at, ChangeCause.REWARDED, rewards)


def _applied(entry: Entry, at: datetime) -> BlueprintApplied:
    grade = required(entry, "Level", int)
    if not 1 <= grade <= 5:
        raise MalformedEntryError("Level")
    return BlueprintApplied(
        at,
        required(entry, "BlueprintName", str),
        grade,
        _symbol(entry, "Module"),
        optional(entry, "EngineerID", int),
        optional(entry, "ApplyExperimentalEffect", str),
        _spent(entry, "Ingredients"),
    )


def _engineer(entry: Entry) -> EngineerState:
    try:
        status = EngineerStatus(required(entry, "Progress", str))
    except ValueError as error:
        raise MalformedEntryError("Progress") from error
    return EngineerState(
        required(entry, "EngineerID", int),
        required(entry, "Engineer", str),
        status,
        optional(entry, "Rank", int),
    )


def _progress(entry: Entry, at: datetime) -> EngineersStated | EngineerProgressed:
    # At start, every engineer in a list; afterwards, one engineer at the top level
    if "Engineers" in entry:
        return EngineersStated(at, tuple(_engineer(item) for item in items(entry, "Engineers")))
    return EngineerProgressed(at, _engineer(entry))


def _closed(_entry: Entry, at: datetime) -> GameClosed:
    return GameClosed(at)


_PARSERS: dict[str, Parser[Fact | None]] = {
    "Materials": _inventory,
    "MaterialCollected": _collected,
    "MaterialDiscarded": _discarded,
    "MaterialTrade": _traded,
    "Synthesis": _synthesised,
    "TechnologyBroker": _broker,
    "EngineerContribution": _contributed,
    "ScientificResearch": _research,
    "MissionCompleted": _rewarded,
    "EngineerCraft": _applied,
    "EngineerProgress": _progress,
    "Shutdown": _closed,
}
