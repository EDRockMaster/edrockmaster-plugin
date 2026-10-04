"""Combat presenter: combat notifications in, panel texts out (ADR 0013)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import assert_never

from edrockmaster.domain.combat.journal import CommunityGoal
from edrockmaster.domain.combat.session import (
    CombatEnded,
    CombatEndReason,
    CombatNotification,
    CombatStarted,
    CombatStats,
    CombatUpdated,
    CommunityGoalsChanged,
    SegmentStats,
    SiteAverage,
    Tally,
    Vouchers,
    VouchersUpdated,
)
from edrockmaster.domain.combat.sites import SiteType
from edrockmaster.ui.panel_model import (
    NumberFormat,
    PanelModel,
    StatLine,
    Translate,
    default_number_format,
    format_credits,
    format_duration,
    identity,
)

GOAL_TITLE_LENGTH = 32
"""Community goal titles can be long: beyond this, they would widen EDMC's window."""

# English source strings, translated at render time
_END_REASONS = {
    CombatEndReason.GAME_CLOSED: "game closed",
    CombatEndReason.DIED: "ship destroyed",
    CombatEndReason.MANUAL: "reset",
}
SITE_NAMES = {
    SiteType.CONFLICT_ZONE_LOW: "Conflict zone, low",
    SiteType.CONFLICT_ZONE_MEDIUM: "Conflict zone, medium",
    SiteType.CONFLICT_ZONE_HIGH: "Conflict zone, high",
    SiteType.RES_LOW: "RES, low",
    SiteType.RES: "RES",
    SiteType.RES_HIGH: "RES, high",
    SiteType.RES_HAZARDOUS: "RES, hazardous",
    SiteType.NAV_BEACON: "Nav beacon",
    SiteType.UNKNOWN: "Unknown site",
}


class CombatPresenter:
    def __init__(
        self, translate: Translate = identity, format_number: NumberFormat = default_number_format
    ) -> None:
        self._tl = translate
        self._number = format_number
        self._running = False
        self._ended: CombatEndReason | None = None
        self._stats: CombatStats | None = None
        self._vouchers: Vouchers | None = None
        self._goals: tuple[CommunityGoal, ...] = ()

    def apply(self, notifications: Iterable[CombatNotification]) -> PanelModel:
        for notification in notifications:
            self._apply(notification)
        return self.render()

    def render(self) -> PanelModel:
        lines = list(self._session_lines(self._stats)) if self._stats else []
        if self._vouchers is not None and self._vouchers.total:
            lines.append(StatLine(self._tl("Unredeemed"), self._credits(self._vouchers.total)))
        lines += [StatLine(_shorten(goal.title), self._goal_text(goal)) for goal in self._goals]
        return PanelModel(
            status=self._status(), lines=tuple(lines), alert=None, can_reset=self._running
        )

    def _apply(self, notification: CombatNotification) -> None:
        match notification:
            case CombatStarted():
                self._running, self._ended, self._stats = True, None, None
            case CombatUpdated(stats=stats):
                self._stats = stats
            case CombatEnded(reason=reason, stats=stats):
                self._running, self._ended, self._stats = False, reason, stats
            case VouchersUpdated(vouchers=vouchers):
                self._vouchers = vouchers
            case CommunityGoalsChanged(goals=goals):
                self._goals = goals
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(notification)

    def _status(self) -> str:
        tl = self._tl
        if self._running:
            current = self._stats.current if self._stats else None
            return tl(SITE_NAMES[current.site]) if current else tl("Combat")
        if self._ended is not None:
            return tl("Combat session ended: {reason}").format(reason=tl(_END_REASONS[self._ended]))
        return tl("No combat session")

    def _session_lines(self, stats: CombatStats) -> Iterable[StatLine]:
        tl, number = self._tl, self._number
        if stats.segments:
            yield StatLine(tl("Active time"), format_duration(stats.active_duration, tl))
        kills = number(stats.kills, 0)
        if stats.shared_kills:
            kills = tl("{kills} ({shared} shared)").format(
                kills=kills, shared=number(stats.shared_kills, 0)
            )
        yield StatLine(tl("Kills"), kills)
        if stats.bounty_credits or not stats.bond_credits:
            # In a conflict zone, only combat bonds are earned: no empty bounty line
            yield StatLine(tl("Bounties"), self._credits(stats.bounty_credits))
        if stats.bond_credits:
            yield StatLine(tl("Combat bonds"), self._credits(stats.bond_credits))
        if stats.current is not None:
            yield StatLine(tl("This site"), self._segment_text(stats.current))
        yield from (self._average_line(average) for average in stats.by_site())
        if stats.miscellaneous != Tally():
            yield StatLine(tl("Miscellaneous"), self._tally_text(stats.miscellaneous))
        if stats.crimes.fines:
            yield StatLine(tl("Fines"), self._credits(stats.crimes.fines))
        if stats.crimes.bounties:
            yield StatLine(tl("Bounty on you"), self._credits(stats.crimes.bounties))

    def _segment_text(self, segment: SegmentStats) -> str:
        return self._tl("{duration}, kills: {kills}").format(
            duration=format_duration(segment.duration, self._tl),
            kills=self._number(segment.tally.kills, 0),
        )

    def _average_line(self, average: SiteAverage) -> StatLine:
        rates = self._tl("{kills} kills/h, {credits}/h").format(
            kills=self._number(average.kills_per_hour, 1),
            credits=self._credits(average.credits_per_hour),
        )
        return StatLine(self._tl(SITE_NAMES[average.site]), rates)

    def _tally_text(self, tally: Tally) -> str:
        return self._tl("kills: {kills}, {credits}").format(
            kills=self._number(tally.kills, 0), credits=self._credits(tally.credits)
        )

    def _goal_text(self, goal: CommunityGoal) -> str:
        tl = self._tl
        parts = [self._number(goal.contribution, 0)]
        if goal.percentile_band is not None:
            parts.append(tl("top {band} %").format(band=goal.percentile_band))
        if goal.tier_reached:
            parts.append(goal.tier_reached)
        text = ", ".join(parts)
        return tl("{goal} (complete)").format(goal=text) if goal.complete else text

    def _credits(self, credits: float) -> str:
        return format_credits(credits, self._tl, self._number)


def _shorten(title: str) -> str:
    if len(title) <= GOAL_TITLE_LENGTH:
        return title
    return title[: GOAL_TITLE_LENGTH - 1].rstrip() + "…"
