"""Community goals presenter: the goals joined in, card texts out (ADR 0032).

One line per goal: its full title and system, the commander's contribution as
the game gives it, the percentile band, the tier reached out of the top tier,
and its expiry, which the interface counts down; once complete, that its reward
is to collect. Not a session: nothing to reset.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from edrockmaster.domain.community_goals.goals import (
    CommunityGoalsChanged,
    CommunityGoalsNotification,
)
from edrockmaster.domain.community_goals.journal import CommunityGoal
from edrockmaster.ui.panel_model import (
    NumberFormat,
    PanelModel,
    StatLine,
    Translate,
    default_number_format,
    identity,
)

_TIER = re.compile(r"\D*(\d+)")
"""A tier as the game names it, ``Tier 3`` or, in older French journals, ``Niveau 3``."""


class CommunityGoalsPresenter:
    def __init__(
        self, translate: Translate = identity, format_number: NumberFormat = default_number_format
    ) -> None:
        self._tl = translate
        self._number = format_number
        self._goals: tuple[CommunityGoal, ...] = ()

    def apply(self, notifications: Iterable[CommunityGoalsNotification]) -> PanelModel:
        for notification in notifications:
            match notification:
                case CommunityGoalsChanged(goals=goals):
                    self._goals = goals
        return self.render()

    def render(self) -> PanelModel:
        return PanelModel(
            status=self._status(),
            lines=tuple(self._line(goal) for goal in self._goals),
            alert=None,
            can_reset=False,
        )

    def _status(self) -> str:
        if not self._goals:
            return self._tl("No community goal joined")
        return self._tl("Goals joined: {count}").format(count=len(self._goals))

    def _line(self, goal: CommunityGoal) -> StatLine:
        # The title often names the system already
        shown = goal.system and goal.system not in goal.title
        label = f"{goal.title}, {goal.system}" if shown else goal.title
        parts = [self._number(goal.contribution, 0)]
        if goal.percentile_band is not None:
            parts.append(self._tl("top {band} %").format(band=goal.percentile_band))
        if goal.tier_reached:
            parts.append(self._tier(goal.tier_reached, goal.top_tier))
        value = ", ".join(parts)
        if goal.complete:
            return StatLine(
                label, self._tl("{goal}. Complete: reward to collect").format(goal=value)
            )
        return StatLine(label, value, until=goal.expiry)

    def _tier(self, reached: str, top: str | None) -> str:
        reached_number = _TIER.fullmatch(reached)
        top_number = _TIER.fullmatch(top) if top else None
        if reached_number is None or top_number is None:
            return reached
        return self._tl("tier {tier} of {top}").format(
            tier=reached_number.group(1), top=top_number.group(1)
        )
