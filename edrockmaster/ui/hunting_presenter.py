"""Bounty hunting presenter: hunting notifications in, panel texts out."""

from __future__ import annotations

from collections.abc import Iterable
from typing import assert_never

from edrockmaster.domain.bounty.hunting import (
    CommunityGoalsChanged,
    HuntEnded,
    HuntEndReason,
    HuntingNotification,
    HuntStarted,
    HuntStats,
    HuntUpdated,
    Vouchers,
    VouchersUpdated,
)
from edrockmaster.domain.bounty.journal import CommunityGoal
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
    HuntEndReason.GAME_CLOSED: "game closed",
    HuntEndReason.DIED: "ship destroyed",
    HuntEndReason.MANUAL: "reset",
}


class HuntingPresenter:
    def __init__(
        self, translate: Translate = identity, format_number: NumberFormat = default_number_format
    ) -> None:
        self._tl = translate
        self._number = format_number
        self._running = False
        self._ended: HuntEndReason | None = None
        self._stats: HuntStats | None = None
        self._vouchers: Vouchers | None = None
        self._goals: tuple[CommunityGoal, ...] = ()

    def apply(self, notifications: Iterable[HuntingNotification]) -> PanelModel:
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

    def _apply(self, notification: HuntingNotification) -> None:
        match notification:
            case HuntStarted():
                self._running, self._ended, self._stats = True, None, None
            case HuntUpdated(stats=stats):
                self._stats = stats
            case HuntEnded(reason=reason, stats=stats):
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
            return tl("Bounty hunting")
        if self._ended is not None:
            return tl("Hunt ended: {reason}").format(reason=tl(_END_REASONS[self._ended]))
        return tl("No hunting session")

    def _session_lines(self, stats: HuntStats) -> Iterable[StatLine]:
        tl, number = self._tl, self._number
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
        yield StatLine(
            tl("Rate"), tl("{credits}/h").format(credits=self._credits(stats.credits_per_hour))
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
