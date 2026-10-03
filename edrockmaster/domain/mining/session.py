"""Mining sessions: lifecycle and statistics.

``MiningTracker`` is the aggregate root: it receives journal facts and decides
when a session starts and ends. Durations are computed from journal
timestamps, never from the wall clock, so replaying a recorded journal always
yields the same statistics.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from types import MappingProxyType
from typing import TypeIs, assert_never

from edrockmaster.domain.commodities import LIMPET, Commodity
from edrockmaster.domain.mining.journal import (
    AsteroidCracked,
    AsteroidProspected,
    CargoChanged,
    CargoEjected,
    CommodityRefined,
    CommoditySold,
    ContentLevel,
    Fact,
    GameLoaded,
    LeaveReason,
    LimpetKind,
    LimpetLaunched,
    MiningAreaLeft,
    RingEntered,
)

IDLE_THRESHOLD = timedelta(minutes=10)
"""A gap between two mining activities longer than this is a pause, not active time."""

type MiningActivity = AsteroidProspected | CommodityRefined | AsteroidCracked | LimpetLaunched
"""Facts that prove the player is mining (and may start a session)."""

type SessionFact = MiningActivity | CargoChanged | CargoEjected
"""Facts a running session takes into account."""

_MINING_LIMPETS = (LimpetKind.PROSPECTOR, LimpetKind.COLLECTOR)


class EndReason(Enum):
    SUPERCRUISE = "supercruise"
    JUMP = "jump"
    DOCKED = "docked"
    GAME_CLOSED = "game_closed"
    MANUAL = "manual"


_END_REASONS = {
    LeaveReason.SUPERCRUISE: EndReason.SUPERCRUISE,
    LeaveReason.JUMP: EndReason.JUMP,
    LeaveReason.DOCKED: EndReason.DOCKED,
    LeaveReason.GAME_CLOSED: EndReason.GAME_CLOSED,
}


@dataclass(frozen=True, slots=True)
class SessionStats:
    """Immutable snapshot of a session's statistics."""

    started_at: datetime
    active_duration: timedelta
    tons_by_commodity: Mapping[Commodity, int]
    refinements: int
    prospected_by_content: Mapping[ContentLevel, int]
    cores_found: int
    cores_cracked: int
    limpets_launched: Mapping[LimpetKind, int]
    ejected_tons: Mapping[Commodity, int]
    cargo_tons: int | None
    limpets_on_board: int | None
    sold_tons: Mapping[Commodity, int]
    credits_earned: int

    @property
    def total_tons(self) -> int:
        return sum(self.tons_by_commodity.values())

    @property
    def prospected_total(self) -> int:
        return sum(self.prospected_by_content.values())

    @property
    def tons_per_hour(self) -> float:
        hours = self.active_duration.total_seconds() / 3600
        return self.total_tons / hours if hours else 0.0

    @property
    def refinements_per_minute(self) -> float:
        minutes = self.active_duration.total_seconds() / 60
        return self.refinements / minutes if minutes else 0.0


@dataclass(frozen=True, slots=True)
class SessionStarted:
    at: datetime
    system: str | None
    ring: str | None


@dataclass(frozen=True, slots=True)
class SessionUpdated:
    stats: SessionStats


@dataclass(frozen=True, slots=True)
class SessionEnded:
    at: datetime
    reason: EndReason
    stats: SessionStats


@dataclass(frozen=True, slots=True)
class SaleRecorded:
    """Mined tons sold, credited to the session that produced them."""

    at: datetime
    commodity: Commodity
    count: int
    credits: int
    stats: SessionStats


type SessionNotification = SessionStarted | SessionUpdated | SessionEnded | SaleRecorded


@dataclass(slots=True)
class MiningSession:
    """A running mining session. Mutated only through ``MiningTracker``."""

    started_at: datetime
    system: str | None
    ring: str | None
    _last_activity: datetime
    _active: timedelta = timedelta(0)
    _tons: Counter[Commodity] = field(default_factory=Counter)
    _prospected: Counter[ContentLevel] = field(default_factory=Counter)
    _cores_found: int = 0
    _cores_cracked: int = 0
    _limpets: Counter[LimpetKind] = field(default_factory=Counter)
    _ejected: Counter[Commodity] = field(default_factory=Counter)
    _cargo_tons: int | None = None
    _limpets_on_board: int | None = None
    _sold: Counter[Commodity] = field(default_factory=Counter)
    _credits: int = 0

    @property
    def stats(self) -> SessionStats:
        return SessionStats(
            started_at=self.started_at,
            active_duration=self._active,
            tons_by_commodity=MappingProxyType(dict(self._tons)),
            refinements=self._tons.total(),
            prospected_by_content=MappingProxyType(dict(self._prospected)),
            cores_found=self._cores_found,
            cores_cracked=self._cores_cracked,
            limpets_launched=MappingProxyType(dict(self._limpets)),
            ejected_tons=MappingProxyType(dict(self._ejected)),
            cargo_tons=self._cargo_tons,
            limpets_on_board=self._limpets_on_board,
            sold_tons=MappingProxyType(dict(self._sold)),
            credits_earned=self._credits,
        )

    def record_activity(self, at: datetime) -> None:
        gap = at - self._last_activity
        if timedelta(0) < gap <= IDLE_THRESHOLD:
            self._active += gap
        self._last_activity = max(self._last_activity, at)

    def unsold_tons(self, commodity: Commodity) -> int:
        """Tons of a commodity mined in this session and neither ejected nor sold yet."""
        return max(0, self._tons[commodity] - self._ejected[commodity] - self._sold[commodity])

    def record_sale(self, commodity: Commodity, count: int, credits: int) -> None:
        self._sold[commodity] += count
        self._credits += credits

    def apply(self, fact: SessionFact) -> None:
        match fact:
            case AsteroidProspected(content=content, motherlode=motherlode):
                self._prospected[content] += 1
                if motherlode is not None:
                    self._cores_found += 1
            case CommodityRefined(commodity=commodity):
                self._tons[commodity] += 1
            case AsteroidCracked():
                self._cores_cracked += 1
            case LimpetLaunched(kind=kind):
                self._limpets[kind] += 1
            case CargoChanged() as cargo:
                self._cargo_tons = cargo.total - cargo.limpets
                self._limpets_on_board = cargo.tons_of(LIMPET)
            case CargoEjected(commodity=commodity, count=count):
                self._ejected[commodity] += count
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(fact)


class MiningTracker:
    """Aggregate root: follows the player and runs mining sessions."""

    def __init__(self) -> None:
        self._session: MiningSession | None = None
        self._previous: MiningSession | None = None
        self._ring: RingEntered | None = None
        self._galaxy_live = True
        self._beta = False

    @property
    def session(self) -> MiningSession | None:
        return self._session

    @property
    def is_live(self) -> bool:
        """Whether the game currently plays in the Live galaxy (not beta, not Legacy)."""
        return self._galaxy_live and not self._beta

    def set_beta(self, beta: bool) -> None:
        self._beta = beta

    def handle(self, fact: Fact) -> list[SessionNotification]:
        match fact:
            case RingEntered() | GameLoaded():
                self._remember_context(fact)
                return []
            case MiningAreaLeft(at=at, reason=reason):
                self._ring = None
                ended = self._end(at, _END_REASONS[reason])
                return [ended] if ended else []
            case _ if self._is_mining_activity(fact):
                return self._on_activity(fact)
            case CargoChanged() | CargoEjected() if self._session is not None:
                self._session.apply(fact)
                return [SessionUpdated(self._session.stats)]
            case CommoditySold():
                recorded = self._on_sale(fact)
                return [recorded] if recorded else []
            case _:
                return []

    def reset(self, at: datetime) -> SessionEnded | None:
        return self._end(at, EndReason.MANUAL)

    def _remember_context(self, fact: RingEntered | GameLoaded) -> None:
        if isinstance(fact, RingEntered):
            self._ring = fact
        else:
            self._galaxy_live = fact.is_live

    @staticmethod
    def _is_mining_activity(fact: Fact) -> TypeIs[MiningActivity]:
        return isinstance(
            fact, AsteroidProspected | CommodityRefined | AsteroidCracked | LimpetLaunched
        )

    def _on_activity(self, fact: MiningActivity) -> list[SessionNotification]:
        notifications: list[SessionNotification] = []
        if self._session is None:
            if isinstance(fact, LimpetLaunched) and fact.kind not in _MINING_LIMPETS:
                return []
            ring = self._ring
            self._session = MiningSession(
                started_at=fact.at,
                system=ring.system if ring else None,
                ring=ring.ring if ring else None,
                _last_activity=fact.at,
            )
            notifications.append(SessionStarted(fact.at, self._session.system, self._session.ring))
        self._session.record_activity(fact.at)
        self._session.apply(fact)
        notifications.append(SessionUpdated(self._session.stats))
        return notifications

    def _on_sale(self, sale: CommoditySold) -> SaleRecorded | None:
        """Credit a sale to the running session, or else to the last one that ended."""
        session = self._session or self._previous
        if session is None:
            return None
        count = min(sale.count, session.unsold_tons(sale.commodity))
        if count == 0:
            return None
        credits = count * sale.unit_price
        session.record_sale(sale.commodity, count, credits)
        return SaleRecorded(sale.at, sale.commodity, count, credits, session.stats)

    def _end(self, at: datetime, reason: EndReason) -> SessionEnded | None:
        if self._session is None:
            return None
        ended = SessionEnded(at=at, reason=reason, stats=self._session.stats)
        self._previous, self._session = self._session, None
        return ended
