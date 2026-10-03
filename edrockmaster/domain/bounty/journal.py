"""Translation of raw journal entries into facts of the bounty hunting domain.

The bounty hunting context's anti-corruption layer for the game journal,
built on the tolerant helpers of the shared kernel (``journal_reading``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from edrockmaster.domain.journal_reading import (
    Entry,
    Parser,
    instant,
    items,
    localised,
    optional,
    required,
    translate,
)

_SUPERPOWER_PREFIX = "$faction_"


class VoucherKind(Enum):
    BOUNTY = "bounty"
    COMBAT_BOND = "combat_bond"


@dataclass(frozen=True, slots=True)
class FactionReward:
    faction: str
    amount: int


@dataclass(frozen=True, slots=True)
class BountyAwarded:
    """A wanted target destroyed: one kill, a bounty voucher per paying faction."""

    at: datetime
    total: int
    rewards: tuple[FactionReward, ...]
    target: str | None
    victim_faction: str | None
    shared: bool


@dataclass(frozen=True, slots=True)
class CombatBondAwarded:
    """A combat bond; ``kill`` is false for bonds earned on a capital ship."""

    at: datetime
    amount: int
    awarding_faction: str
    victim_faction: str | None
    kill: bool


@dataclass(frozen=True, slots=True)
class VouchersRedeemed:
    at: datetime
    kind: VoucherKind
    amount: int
    by_faction: tuple[FactionReward, ...]


@dataclass(frozen=True, slots=True)
class CommanderDied:
    at: datetime


@dataclass(frozen=True, slots=True)
class GameClosed:
    at: datetime


@dataclass(frozen=True, slots=True)
class CommunityGoal:
    cgid: int
    title: str
    system: str | None
    expiry: datetime | None
    complete: bool
    contribution: int
    percentile_band: int | None
    tier_reached: str | None
    top_tier: str | None


@dataclass(frozen=True, slots=True)
class CommunityGoalsUpdated:
    """The community goals the commander has joined, as the game reports them."""

    at: datetime
    goals: tuple[CommunityGoal, ...]


type Fact = (
    BountyAwarded
    | CombatBondAwarded
    | VouchersRedeemed
    | CommanderDied
    | GameClosed
    | CommunityGoalsUpdated
)


def parse_entry(entry: Entry) -> Fact | None:
    """Return the bounty hunting fact carried by a journal entry, or ``None`` if irrelevant."""
    return translate(entry, _PARSERS)


def faction_name(raw: str) -> str:
    """Superpowers come as ``$faction_Federation;`` in some events: keep the name only."""
    if raw.startswith(_SUPERPOWER_PREFIX) and raw.endswith(";"):
        return raw.removeprefix(_SUPERPOWER_PREFIX).removesuffix(";")
    return raw


def _faction(entry: Entry, name: str) -> str:
    return faction_name(localised(entry, name))


def _optional_faction(entry: Entry, name: str) -> str | None:
    return _faction(entry, name) if name in entry or f"{name}_Localised" in entry else None


def _rewards(entry: Entry, list_name: str, amount_name: str) -> tuple[FactionReward, ...]:
    return tuple(
        FactionReward(_faction(item, "Faction"), required(item, amount_name, int))
        for item in items(entry, list_name)
    )


def _bounty(entry: Entry, at: datetime) -> BountyAwarded:
    if "Rewards" in entry:
        rewards = _rewards(entry, "Rewards", "Reward")
        total = required(entry, "TotalReward", int)
    else:
        total = required(entry, "Reward", int)
        rewards = (FactionReward(_faction(entry, "Faction"), total),)
    target = localised(entry, "Target") if "Target" in entry else None
    return BountyAwarded(
        at=at,
        total=total,
        rewards=rewards,
        target=target,
        victim_faction=_optional_faction(entry, "VictimFaction"),
        shared=bool(optional(entry, "SharedWithOthers", int)),
    )


def _bond(entry: Entry, at: datetime, kill: bool) -> CombatBondAwarded:
    return CombatBondAwarded(
        at=at,
        amount=required(entry, "Reward", int),
        awarding_faction=_faction(entry, "AwardingFaction"),
        victim_faction=_optional_faction(entry, "VictimFaction"),
        kill=kill,
    )


def _kill_bond(entry: Entry, at: datetime) -> CombatBondAwarded:
    return _bond(entry, at, kill=True)


def _capital_ship_bond(entry: Entry, at: datetime) -> CombatBondAwarded:
    return _bond(entry, at, kill=False)


_VOUCHER_KINDS = {"bounty": VoucherKind.BOUNTY, "combatbond": VoucherKind.COMBAT_BOND}


def _redeemed(entry: Entry, at: datetime) -> VouchersRedeemed | None:
    kind = _VOUCHER_KINDS.get(required(entry, "Type", str).lower())
    if kind is None:
        return None
    amount = required(entry, "Amount", int)
    if "Factions" in entry:
        by_faction = _rewards(entry, "Factions", "Amount")
    else:
        by_faction = (FactionReward(_faction(entry, "Faction"), amount),)
    return VouchersRedeemed(at=at, kind=kind, amount=amount, by_faction=by_faction)


def _died(_entry: Entry, at: datetime) -> CommanderDied:
    return CommanderDied(at)


def _closed(_entry: Entry, at: datetime) -> GameClosed:
    return GameClosed(at)


def _goal(item: Entry) -> CommunityGoal:
    top_tier = item.get("TopTier")
    return CommunityGoal(
        cgid=required(item, "CGID", int),
        title=required(item, "Title", str),
        system=optional(item, "SystemName", str),
        expiry=instant(item, "Expiry") if "Expiry" in item else None,
        complete=bool(optional(item, "IsComplete", bool)),
        contribution=optional(item, "PlayerContribution", int) or 0,
        percentile_band=optional(item, "PlayerPercentileBand", int),
        tier_reached=optional(item, "TierReached", str),
        top_tier=optional(top_tier, "Name", str) if isinstance(top_tier, dict) else None,
    )


def _goals(entry: Entry, at: datetime) -> CommunityGoalsUpdated:
    return CommunityGoalsUpdated(
        at=at, goals=tuple(_goal(item) for item in items(entry, "CurrentGoals"))
    )


_PARSERS: dict[str, Parser[Fact | None]] = {
    "Bounty": _bounty,
    "FactionKillBond": _kill_bond,
    "CapShipBond": _capital_ship_bond,
    "RedeemVoucher": _redeemed,
    "Died": _died,
    "Shutdown": _closed,
    "ShutDown": _closed,  # synthetic event from EDMC when the game crashed
    "CommunityGoal": _goals,
}
