"""Hunting sessions, vouchers and community goals.

``HuntingTracker`` is the aggregate root of the bounty hunting context. Like
mining, durations come from journal timestamps, never from the wall clock, so
that a replayed journal yields the same statistics.

Active time is the **time on site**: in normal space away from stations, from
the arrival on the site of the first reward. Searching for targets counts,
travelling and docking do not. (Gaps between rewards, as for mining, made a
20-minute search vanish and the rate soar: see the bounty replay.)

Vouchers are only known from the moment EDMC started: the journal does not
restate the vouchers earned before.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from types import MappingProxyType
from typing import assert_never

from edrockmaster.domain.bounty.journal import (
    BountyAwarded,
    CombatBondAwarded,
    CommanderDied,
    CommunityGoal,
    CommunityGoalsUpdated,
    Fact,
    FactionReward,
    GameClosed,
    SiteEntered,
    SiteLeft,
    VoucherKind,
    VouchersRedeemed,
)

type Reward = BountyAwarded | CombatBondAwarded


class HuntEndReason(Enum):
    GAME_CLOSED = "game_closed"
    DIED = "died"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class HuntStats:
    started_at: datetime
    active_duration: timedelta
    kills: int
    shared_kills: int
    bounty_credits: int
    bond_credits: int

    @property
    def credits(self) -> int:
        return self.bounty_credits + self.bond_credits

    @property
    def credits_per_hour(self) -> float:
        hours = self.active_duration.total_seconds() / 3600
        return self.credits / hours if hours else 0.0

    @property
    def kills_per_hour(self) -> float:
        hours = self.active_duration.total_seconds() / 3600
        return self.kills / hours if hours else 0.0


@dataclass(frozen=True, slots=True)
class Vouchers:
    """Unredeemed vouchers, by paying faction."""

    bounties: Mapping[str, int]
    combat_bonds: Mapping[str, int]

    @property
    def total(self) -> int:
        return sum(self.bounties.values()) + sum(self.combat_bonds.values())


@dataclass(frozen=True, slots=True)
class HuntStarted:
    at: datetime


@dataclass(frozen=True, slots=True)
class HuntUpdated:
    stats: HuntStats


@dataclass(frozen=True, slots=True)
class HuntEnded:
    at: datetime
    reason: HuntEndReason
    stats: HuntStats


@dataclass(frozen=True, slots=True)
class VouchersUpdated:
    vouchers: Vouchers


@dataclass(frozen=True, slots=True)
class CommunityGoalsChanged:
    goals: tuple[CommunityGoal, ...]


type HuntingNotification = (
    HuntStarted | HuntUpdated | HuntEnded | VouchersUpdated | CommunityGoalsChanged
)


class HuntingSession:
    """A running hunting session. Mutated only through ``HuntingTracker``."""

    def __init__(self, started_at: datetime, on_site_since: datetime | None) -> None:
        self.started_at = started_at
        self._on_site_since: datetime | None = on_site_since or started_at
        self._last_seen = started_at
        self._time_on_site = timedelta(0)
        self._kills = 0
        self._shared_kills = 0
        self._bounty_credits = 0
        self._bond_credits = 0

    @property
    def stats(self) -> HuntStats:
        current = self._last_seen - self._on_site_since if self._on_site_since else timedelta(0)
        return HuntStats(
            started_at=self.started_at,
            active_duration=self._time_on_site + max(current, timedelta(0)),
            kills=self._kills,
            shared_kills=self._shared_kills,
            bounty_credits=self._bounty_credits,
            bond_credits=self._bond_credits,
        )

    def site_entered(self, at: datetime) -> None:
        self._see(at)
        if self._on_site_since is None:
            self._on_site_since = at

    def site_left(self, at: datetime) -> None:
        self._see(at)
        if self._on_site_since is not None:
            self._time_on_site += max(at - self._on_site_since, timedelta(0))
            self._on_site_since = None

    def apply(self, reward: Reward) -> None:
        self._see(reward.at)
        if self._on_site_since is None:  # a site the journal did not tell
            self._on_site_since = reward.at
        match reward:
            case BountyAwarded(total=total, shared=shared):
                self._kills += 1
                self._shared_kills += shared
                self._bounty_credits += total
            case CombatBondAwarded(amount=amount, kill=kill):
                self._kills += kill
                self._bond_credits += amount
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(reward)

    def _see(self, at: datetime) -> None:
        self._last_seen = max(self._last_seen, at)


class HuntingTracker:
    """Aggregate root: follows the commander's kills, vouchers and community goals."""

    def __init__(self) -> None:
        self._session: HuntingSession | None = None
        self._on_site_since: datetime | None = None
        self._bounties: Counter[str] = Counter()
        self._bonds: Counter[str] = Counter()
        self._goals: tuple[CommunityGoal, ...] = ()

    @property
    def session(self) -> HuntingSession | None:
        return self._session

    @property
    def vouchers(self) -> Vouchers:
        return Vouchers(
            bounties=MappingProxyType(dict(+self._bounties)),
            combat_bonds=MappingProxyType(dict(+self._bonds)),
        )

    @property
    def community_goals(self) -> tuple[CommunityGoal, ...]:
        return self._goals

    def handle(self, fact: Fact) -> list[HuntingNotification]:
        match fact:
            case BountyAwarded() | CombatBondAwarded():
                return self._on_reward(fact)
            case VouchersRedeemed(kind=kind, by_faction=paid):
                self._redeem(
                    self._bonds if kind is VoucherKind.COMBAT_BOND else self._bounties, paid
                )
                return [VouchersUpdated(self.vouchers)]
            case CommanderDied(at=at):
                return self._on_death(at)
            case GameClosed(at=at):
                return self._ended(at, HuntEndReason.GAME_CLOSED)
            case SiteEntered() | SiteLeft():
                return self._on_site(fact)
            case CommunityGoalsUpdated(goals=goals):
                self._goals = goals
                return [CommunityGoalsChanged(goals)]
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(fact)

    def reset(self, at: datetime) -> HuntEnded | None:
        return self._end(at, HuntEndReason.MANUAL)

    def _on_site(self, fact: SiteEntered | SiteLeft) -> list[HuntingNotification]:
        if isinstance(fact, SiteEntered):
            self._on_site_since = fact.at
            if self._session is not None:
                self._session.site_entered(fact.at)
            return []
        self._on_site_since = None
        if self._session is None:
            return []
        self._session.site_left(fact.at)
        return [HuntUpdated(self._session.stats)]

    def _on_death(self, at: datetime) -> list[HuntingNotification]:
        notifications = self._ended(at, HuntEndReason.DIED)
        if self.vouchers.total:
            self._bounties.clear()
            self._bonds.clear()
            notifications.append(VouchersUpdated(self.vouchers))
        return notifications

    def _on_reward(self, reward: Reward) -> list[HuntingNotification]:
        notifications: list[HuntingNotification] = []
        if self._session is None:
            self._session = HuntingSession(reward.at, self._on_site_since)
            notifications.append(HuntStarted(reward.at))
        self._session.apply(reward)
        if isinstance(reward, BountyAwarded):
            self._earn(self._bounties, reward.rewards)
        else:
            self._earn(self._bonds, (FactionReward(reward.awarding_faction, reward.amount),))
        notifications += [HuntUpdated(self._session.stats), VouchersUpdated(self.vouchers)]
        return notifications

    @staticmethod
    def _earn(vouchers: Counter[str], rewards: Iterable[FactionReward]) -> None:
        for reward in rewards:
            vouchers[reward.faction] += reward.amount

    @staticmethod
    def _redeem(vouchers: Counter[str], paid: Iterable[FactionReward]) -> None:
        # Vouchers earned before EDMC started are unknown: never go below zero
        for reward in paid:
            vouchers[reward.faction] = max(0, vouchers[reward.faction] - reward.amount)

    def _ended(self, at: datetime, reason: HuntEndReason) -> list[HuntingNotification]:
        ended = self._end(at, reason)
        return [ended] if ended else []

    def _end(self, at: datetime, reason: HuntEndReason) -> HuntEnded | None:
        if reason is not HuntEndReason.MANUAL:
            self._on_site_since = None
        if self._session is None:
            return None
        self._session.site_left(at)
        ended = HuntEnded(at=at, reason=reason, stats=self._session.stats)
        self._session = None
        return ended
