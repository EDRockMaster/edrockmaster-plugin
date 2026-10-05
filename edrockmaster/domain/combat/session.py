"""Combat sessions by site segments, vouchers, crimes and community goals (ADR 0013).

``CombatTracker`` is the aggregate root of the combat context. Durations come
from journal timestamps, never from the wall clock, so that a replayed journal
yields the same statistics.

A **segment** is one stay on a combat site (a conflict zone, a resource
extraction site, a navigation beacon), from the arrival to the departure. It
opens with the first reward on that site, counting from the arrival: the
search for targets is part of the fight. A site left without any reward is
not counted. Rates are averaged per site type, weighted by time.

A kill anywhere else (a pirate shot down while mining, after an interdiction,
near a station) is **miscellaneous**: counted in the totals, in no rate, since
no time belongs to it. When EDMC starts on a site, the arrival was not seen:
the first reward opens a segment of type ``UNKNOWN`` from that reward, unless
the commander mines there.

A combat bond only exists in a conflict zone (ADR 0015): outside any segment,
it opens one from the commander's last arrival, or from the bond when no
arrival was seen. By ship, it is a conflict zone of unknown intensity; on foot,
a ground conflict zone. The dropship to a ground conflict zone is an arrival on
that site, and its retreat a departure.

Vouchers are only known from the moment EDMC started: the journal does not
restate the vouchers earned before.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from types import MappingProxyType
from typing import assert_never

from edrockmaster.domain.combat.journal import (
    BountyAwarded,
    CombatBondAwarded,
    CommanderDied,
    CommunityGoal,
    CommunityGoalsUpdated,
    CrimeCommitted,
    DestinationDropped,
    Embarked,
    Fact,
    FactionReward,
    GameClosed,
    GameLoaded,
    MiningSeen,
    NormalSpaceEntered,
    OnFootArrived,
    SettlementApproached,
    SiteLeft,
    VoucherKind,
    VouchersRedeemed,
)
from edrockmaster.domain.combat.sites import SiteType

type Reward = BountyAwarded | CombatBondAwarded


class CombatEndReason(Enum):
    GAME_CLOSED = "game_closed"
    DIED = "died"
    MANUAL = "manual"


def _per_hour(count: float, duration: timedelta) -> float:
    hours = duration.total_seconds() / 3600
    return count / hours if hours else 0.0


@dataclass(frozen=True, slots=True)
class Tally:
    """What a set of rewards adds up to."""

    kills: int = 0
    shared_kills: int = 0
    bounty_credits: int = 0
    bond_credits: int = 0

    @property
    def credits(self) -> int:
        return self.bounty_credits + self.bond_credits

    def __add__(self, other: Tally) -> Tally:
        return Tally(
            kills=self.kills + other.kills,
            shared_kills=self.shared_kills + other.shared_kills,
            bounty_credits=self.bounty_credits + other.bounty_credits,
            bond_credits=self.bond_credits + other.bond_credits,
        )

    def counting(self, reward: Reward) -> Tally:
        match reward:
            case BountyAwarded(total=total, shared=shared):
                return self + Tally(kills=1, shared_kills=int(shared), bounty_credits=total)
            case CombatBondAwarded(amount=amount, kill=kill):
                return self + Tally(kills=int(kill), bond_credits=amount)
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(reward)


@dataclass(frozen=True, slots=True)
class SegmentStats:
    site: SiteType
    started_at: datetime
    duration: timedelta
    tally: Tally
    settlement: str | None = None
    """The settlement of a ground conflict zone, when supercruise named it."""

    @property
    def kills_per_hour(self) -> float:
        return _per_hour(self.tally.kills, self.duration)

    @property
    def credits_per_hour(self) -> float:
        return _per_hour(self.tally.credits, self.duration)


@dataclass(frozen=True, slots=True)
class SiteAverage:
    """All the segments of a site type: their rates, weighted by time."""

    site: SiteType
    duration: timedelta
    tally: Tally

    @property
    def kills_per_hour(self) -> float:
        return _per_hour(self.tally.kills, self.duration)

    @property
    def credits_per_hour(self) -> float:
        return _per_hour(self.tally.credits, self.duration)


@dataclass(frozen=True, slots=True)
class Crimes:
    """Fines and bounties on the commander's head: never deducted from what was earned."""

    count: int = 0
    fines: int = 0
    bounties: int = 0
    by_kind: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class CombatStats:
    started_at: datetime
    segments: tuple[SegmentStats, ...]
    """Closed segments, then the current one, if any."""
    current: SegmentStats | None
    miscellaneous: Tally
    crimes: Crimes

    @property
    def active_duration(self) -> timedelta:
        return sum((segment.duration for segment in self.segments), timedelta(0))

    @property
    def on_site(self) -> Tally:
        return sum((segment.tally for segment in self.segments), Tally())

    @property
    def total(self) -> Tally:
        return self.on_site + self.miscellaneous

    @property
    def kills(self) -> int:
        return self.total.kills

    @property
    def shared_kills(self) -> int:
        return self.total.shared_kills

    @property
    def bounty_credits(self) -> int:
        return self.total.bounty_credits

    @property
    def bond_credits(self) -> int:
        return self.total.bond_credits

    @property
    def credits(self) -> int:
        return self.total.credits

    @property
    def kills_per_hour(self) -> float:
        return _per_hour(self.on_site.kills, self.active_duration)

    @property
    def credits_per_hour(self) -> float:
        return _per_hour(self.on_site.credits, self.active_duration)

    def by_site(self) -> tuple[SiteAverage, ...]:
        """One average per site type, in the order of the first visit."""
        durations: dict[SiteType, timedelta] = {}
        tallies: dict[SiteType, Tally] = {}
        for segment in self.segments:
            durations[segment.site] = durations.get(segment.site, timedelta(0)) + segment.duration
            tallies[segment.site] = tallies.get(segment.site, Tally()) + segment.tally
        return tuple(SiteAverage(site, durations[site], tallies[site]) for site in durations)


@dataclass(frozen=True, slots=True)
class Vouchers:
    """Unredeemed vouchers, by paying faction."""

    bounties: Mapping[str, int]
    combat_bonds: Mapping[str, int]

    @property
    def total(self) -> int:
        return sum(self.bounties.values()) + sum(self.combat_bonds.values())


@dataclass(frozen=True, slots=True)
class CombatStarted:
    at: datetime


@dataclass(frozen=True, slots=True)
class CombatUpdated:
    stats: CombatStats


@dataclass(frozen=True, slots=True)
class CombatEnded:
    at: datetime
    reason: CombatEndReason
    stats: CombatStats


@dataclass(frozen=True, slots=True)
class VouchersUpdated:
    vouchers: Vouchers


@dataclass(frozen=True, slots=True)
class CommunityGoalsChanged:
    goals: tuple[CommunityGoal, ...]


type CombatNotification = (
    CombatStarted | CombatUpdated | CombatEnded | VouchersUpdated | CommunityGoalsChanged
)


@dataclass(slots=True)
class _OpenSegment:
    site: SiteType
    since: datetime
    settlement: str | None = None
    tally: Tally = Tally()

    def stats(self, until: datetime) -> SegmentStats:
        return SegmentStats(
            self.site,
            self.since,
            max(until - self.since, timedelta(0)),
            self.tally,
            self.settlement,
        )


class CombatSession:
    """A running combat session. Mutated only through ``CombatTracker``."""

    def __init__(self, started_at: datetime) -> None:
        self.started_at = started_at
        self._last_seen = started_at
        self._closed: list[SegmentStats] = []
        self._open: _OpenSegment | None = None
        self._miscellaneous = Tally()
        self._crimes: Counter[str] = Counter()
        self._fines = 0
        self._bounties = 0

    @property
    def stats(self) -> CombatStats:
        current = self._open.stats(self._last_seen) if self._open else None
        return CombatStats(
            started_at=self.started_at,
            segments=(*self._closed, current) if current else tuple(self._closed),
            current=current,
            miscellaneous=self._miscellaneous,
            crimes=Crimes(
                count=self._crimes.total(),
                fines=self._fines,
                bounties=self._bounties,
                by_kind=MappingProxyType(dict(self._crimes)),
            ),
        )

    @property
    def on_segment(self) -> bool:
        return self._open is not None

    def see(self, at: datetime) -> None:
        self._last_seen = max(self._last_seen, at)

    def open_segment(self, site: SiteType, since: datetime, settlement: str | None = None) -> None:
        self._open = _OpenSegment(site, since, settlement)

    def close_segment(self, at: datetime) -> bool:
        """Close the current segment, if any; ``True`` when one was closed."""
        if self._open is None:
            return False
        self.see(at)
        self._closed.append(self._open.stats(at))
        self._open = None
        return True

    def apply(self, reward: Reward) -> None:
        self.see(reward.at)
        if self._open is not None:
            self._open.tally = self._open.tally.counting(reward)
        else:
            self._miscellaneous = self._miscellaneous.counting(reward)

    def record_crime(self, crime: CrimeCommitted) -> None:
        self.see(crime.at)
        self._crimes[crime.kind] += 1
        self._fines += crime.fine
        self._bounties += crime.bounty


class _Place(Enum):
    NOWHERE = auto()
    """In supercruise, in hyperspace or docked."""
    COMBAT_SITE = auto()
    OTHER = auto()
    """In normal space, somewhere the journal named and that is not a combat site."""
    UNKNOWN = auto()
    """In normal space, arrival not seen: EDMC or the game just started."""


type _Segment = tuple[SiteType, datetime, str | None]
"""What a reward opens: site type, start and settlement."""


class CombatTracker:
    """Aggregate root: follows the commander's combat, vouchers, crimes and community goals."""

    def __init__(self) -> None:
        self._session: CombatSession | None = None
        self._place = _Place.UNKNOWN
        self._site: SiteType | None = None
        self._since: datetime | None = None
        self._dropped: SiteType | None = None
        self._on_foot = False
        self._settlement: str | None = None
        self._mining_here = False
        self._bounties: Counter[str] = Counter()
        self._bonds: Counter[str] = Counter()
        self._goals: tuple[CommunityGoal, ...] = ()

    @property
    def session(self) -> CombatSession | None:
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

    def handle(self, fact: Fact) -> list[CombatNotification]:
        match fact:
            case BountyAwarded() | CombatBondAwarded():
                return self._on_reward(fact)
            case (
                DestinationDropped()
                | NormalSpaceEntered()
                | GameLoaded()
                | SiteLeft()
                | OnFootArrived()
                | Embarked()
                | SettlementApproached()
            ):
                return self._on_move(fact)
            case MiningSeen() | CrimeCommitted():
                return self._on_conduct(fact)
            case VouchersRedeemed() | CommunityGoalsUpdated():
                return self._on_records(fact)
            case CommanderDied() | GameClosed():
                return self._on_exit(fact)
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(fact)

    def reset(self, at: datetime) -> CombatEnded | None:
        if self._since is not None:
            self._since = at  # a later segment on this site starts now
        return self._end(at, CombatEndReason.MANUAL)

    def _arrive(
        self, place: _Place, at: datetime | None, site: SiteType | None, on_foot: bool = False
    ) -> None:
        self._place, self._since, self._site = place, at, site
        self._on_foot = on_foot
        self._mining_here = False

    def _on_move(
        self,
        fact: DestinationDropped
        | NormalSpaceEntered
        | GameLoaded
        | SiteLeft
        | OnFootArrived
        | Embarked
        | SettlementApproached,
    ) -> list[CombatNotification]:
        match fact:
            case DestinationDropped(site=site):
                self._dropped = site  # the arrival follows at once
            case NormalSpaceEntered(at=at):
                site, self._dropped = self._dropped, None
                self._arrive(_Place.COMBAT_SITE if site else _Place.OTHER, at, site)
            case GameLoaded(docked=docked, on_foot=on_foot):
                self._settlement = None
                place = _Place.NOWHERE if docked else _Place.UNKNOWN
                self._arrive(place, None, None, on_foot=on_foot)
            case OnFootArrived(at=at, dropship=True):
                if self._site is not SiteType.GROUND_CONFLICT_ZONE:  # else, a redeploy
                    self._arrive(_Place.COMBAT_SITE, at, SiteType.GROUND_CONFLICT_ZONE, True)
            case OnFootArrived(at=at):
                self._arrive(_Place.OTHER, at, None, on_foot=True)
            case Embarked(at=at, on_station=on_station):
                self._arrive(_Place.NOWHERE if on_station else _Place.OTHER, at, None)
                return self._close_segment(at)
            case SettlementApproached(name=name):
                self._settlement = name
            case SiteLeft(at=at):
                self._settlement = None
                self._arrive(_Place.NOWHERE, None, None)
                return self._close_segment(at)
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(fact)
        return []

    def _on_conduct(self, fact: MiningSeen | CrimeCommitted) -> list[CombatNotification]:
        if isinstance(fact, MiningSeen):
            self._mining_here = True
            return []
        if self._session is None:
            return []
        self._session.record_crime(fact)
        return [CombatUpdated(self._session.stats)]

    def _on_records(
        self, fact: VouchersRedeemed | CommunityGoalsUpdated
    ) -> list[CombatNotification]:
        if isinstance(fact, CommunityGoalsUpdated):
            self._goals = fact.goals
            return [CommunityGoalsChanged(fact.goals)]
        vouchers = self._bonds if fact.kind is VoucherKind.COMBAT_BOND else self._bounties
        self._redeem(vouchers, fact.by_faction)
        return [VouchersUpdated(self.vouchers)]

    def _on_exit(self, fact: CommanderDied | GameClosed) -> list[CombatNotification]:
        if isinstance(fact, CommanderDied):
            return self._on_death(fact.at)
        self._arrive(_Place.UNKNOWN, None, None)
        return self._ended(fact.at, CombatEndReason.GAME_CLOSED)

    def _close_segment(self, at: datetime) -> list[CombatNotification]:
        if self._session is None or not self._session.close_segment(at):
            return []
        return [CombatUpdated(self._session.stats)]

    def _segment_for(self, reward: Reward) -> _Segment | None:
        """The segment a reward opens, if it falls on a combat site."""
        if self._place is _Place.COMBAT_SITE and self._site and self._since:
            return self._site, self._since, self._ground_settlement(self._site)
        if isinstance(reward, CombatBondAwarded) and reward.kill:
            return self._conflict_zone_for(reward)
        if self._place is _Place.UNKNOWN and not self._mining_here:
            return SiteType.UNKNOWN, reward.at, None
        return None

    def _conflict_zone_for(self, bond: CombatBondAwarded) -> _Segment | None:
        """A kill bond only exists in a conflict zone, even where no drop named one."""
        if self._place is _Place.NOWHERE:
            return None
        site = SiteType.GROUND_CONFLICT_ZONE if self._on_foot else SiteType.CONFLICT_ZONE_UNKNOWN
        since = self._since if self._place is _Place.OTHER and self._since else bond.at
        return site, since, self._ground_settlement(site)

    def _ground_settlement(self, site: SiteType) -> str | None:
        return self._settlement if site is SiteType.GROUND_CONFLICT_ZONE else None

    def _on_reward(self, reward: Reward) -> list[CombatNotification]:
        notifications: list[CombatNotification] = []
        if self._session is None:
            self._session = CombatSession(reward.at)
            notifications.append(CombatStarted(reward.at))
        if not self._session.on_segment and (segment := self._segment_for(reward)):
            self._session.open_segment(*segment)
        self._session.apply(reward)
        if isinstance(reward, BountyAwarded):
            self._earn(self._bounties, reward.rewards)
        else:
            self._earn(self._bonds, (FactionReward(reward.awarding_faction, reward.amount),))
        notifications += [CombatUpdated(self._session.stats), VouchersUpdated(self.vouchers)]
        return notifications

    def _on_death(self, at: datetime) -> list[CombatNotification]:
        self._settlement = None
        self._arrive(_Place.NOWHERE, None, None)
        notifications = self._ended(at, CombatEndReason.DIED)
        if self.vouchers.total:
            self._bounties.clear()
            self._bonds.clear()
            notifications.append(VouchersUpdated(self.vouchers))
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

    def _ended(self, at: datetime, reason: CombatEndReason) -> list[CombatNotification]:
        ended = self._end(at, reason)
        return [ended] if ended else []

    def _end(self, at: datetime, reason: CombatEndReason) -> CombatEnded | None:
        if self._session is None:
            return None
        self._session.close_segment(at)
        self._session.see(at)
        ended = CombatEnded(at=at, reason=reason, stats=self._session.stats)
        self._session = None
        return ended
