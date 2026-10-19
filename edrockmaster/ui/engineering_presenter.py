"""Engineering presenter: engineering notifications in, panel texts out (ADR 0017).

The panel block sums up the collection: materials gained per category, used,
those at their cap, on-foot materials gained and lost at a death in one tile
(ADR 0027; their kinds are in the On foot view), and the goals ready, then
the first goals in the player's priority, each ready or what it misses
(ADR 0033), and how many more. Its
alert is the last material that reached its cap, goal ready or goal done, until
the next change without one; a ready goal's alert also goes when the goal is no
longer among the goals.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import assert_never

from edrockmaster.domain.engineering.catalogue import MaterialCategory
from edrockmaster.domain.engineering.collection import CollectionEndReason, CollectionStats
from edrockmaster.domain.engineering.events import (
    CollectionEnded,
    CollectionStarted,
    EngineeringNotification,
    EngineeringStats,
    EngineeringUpdated,
    GoalDone,
    GoalProgressed,
    GoalReady,
    MaterialCapped,
)
from edrockmaster.domain.engineering.progress import GoalProgress
from edrockmaster.ui.engineering_names import EngineeringNames
from edrockmaster.ui.panel_model import (
    NumberFormat,
    PanelModel,
    StatLine,
    Translate,
    default_number_format,
    identity,
)

# English source strings, translated at render time
_GAINED = {
    MaterialCategory.RAW: "Raw gained",
    MaterialCategory.MANUFACTURED: "Manufactured gained",
    MaterialCategory.ENCODED: "Encoded gained",
    None: "Other materials gained",
}
SUMMARISED_GOALS = 3
"""The goals the card names, first in the priority; the others are counted."""

_END_REASONS = {
    CollectionEndReason.GAME_CLOSED: "game closed",
    CollectionEndReason.MANUAL: "reset",
}


class EngineeringPresenter:
    def __init__(
        self,
        names: EngineeringNames,
        translate: Translate = identity,
        format_number: NumberFormat = default_number_format,
    ) -> None:
        self._names = names
        self._tl = translate
        self._number = format_number
        self._running = False
        self._ended: CollectionEndReason | None = None
        self._stats: EngineeringStats | None = None
        self._alert: EngineeringNotification | None = None

    def apply(self, notifications: Iterable[EngineeringNotification]) -> PanelModel:
        batch = list(notifications)
        alerts = [n for n in batch if isinstance(n, MaterialCapped | GoalReady | GoalDone)]
        progressed = any(isinstance(n, EngineeringUpdated) and n.progressed for n in batch)
        if alerts:
            self._alert = alerts[-1]
        elif progressed:
            self._alert = None
        for notification in batch:
            self._apply(notification)
        self._forget_removed_goal()
        return self.render()

    def _forget_removed_goal(self) -> None:
        """A ready goal the player removed no longer has anything to alert about."""
        if isinstance(self._alert, GoalReady) and self._stats is not None:
            kept = {progress.goal.id for progress in self._stats.goals}
            if self._alert.goal.id not in kept:
                self._alert = None

    def render(self) -> PanelModel:
        return PanelModel(
            status=self._status(),
            lines=tuple(self._lines(self._stats)) if self._stats else (),
            alert=self._alert_text(),
            can_reset=self._running,
        )

    def forget_ended(self) -> None:
        """The collection ended belongs to a past game: no longer shown (the goals stay)."""
        if not self._running:
            self._ended = None

    def _apply(self, notification: EngineeringNotification) -> None:
        match notification:
            case CollectionStarted():
                self._running, self._ended = True, None
            case CollectionEnded(reason=reason):
                self._running, self._ended = False, reason
            case EngineeringUpdated(stats=stats):
                self._stats = stats
            case MaterialCapped() | GoalReady() | GoalProgressed() | GoalDone():
                pass
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(notification)

    def _status(self) -> str:
        tl = self._tl
        if self._running:
            return tl("Engineering")
        if self._ended is not None:
            return tl("Engineering session ended: {reason}").format(
                reason=tl(_END_REASONS[self._ended])
            )
        return tl("No engineering session")

    def _lines(self, stats: EngineeringStats) -> Iterable[StatLine]:
        tl = self._tl
        if stats.collection is not None:
            collection = stats.collection
            for category, label in _GAINED.items():
                if collection.gained.get(category):
                    yield StatLine(tl(label), self._number(collection.gained[category], 0))
            if collection.used:
                yield StatLine(tl("Materials used"), self._number(collection.used, 0))
            if collection.capped:
                capped = ", ".join(self._names.material(symbol) for symbol in collection.capped)
                yield StatLine(tl("At cap"), capped)
            gained_on_foot = sum(collection.gained_on_foot.values())
            if gained_on_foot or collection.lost_on_foot:
                yield StatLine(tl("On-foot materials"), self._on_foot_text(collection))
        if stats.goals:
            ready = tl("{ready} of {total}").format(ready=stats.goals_ready, total=len(stats.goals))
            if not stats.inventory_known:
                ready = tl("inventory unknown")
            yield StatLine(tl("Goals ready"), ready)
            for progress in stats.goals[:SUMMARISED_GOALS]:
                yield StatLine(self._names.goal(progress.goal), self._goal_text(progress))
            if len(stats.goals) > SUMMARISED_GOALS:
                more = len(stats.goals) - SUMMARISED_GOALS
                yield StatLine(tl("Other goals"), self._number(more, 0))

    def _goal_text(self, progress: GoalProgress) -> str:
        state = self._goal_state(progress)
        if state is not None or progress.missing is None:
            return state or self._tl("inventory unknown")
        units = self._number(sum(progress.missing.values()), 0)
        if len(progress.missing) == 1:
            [symbol] = progress.missing
            return self._tl("missing {count} {material}").format(
                count=units, material=self._names.material(symbol)
            )
        return self._tl("missing {units} units of {materials} materials").format(
            units=units, materials=len(progress.missing)
        )

    def _on_foot_text(self, collection: CollectionStats) -> str:
        """One tile: the kinds are in the On foot view."""
        text = "+" + self._number(sum(collection.gained_on_foot.values()), 0)
        if not collection.lost_on_foot:
            return text
        return self._tl("{gained}, {lost} lost").format(
            gained=text, lost=self._number(collection.lost_on_foot, 0)
        )

    def _goal_state(self, progress: GoalProgress) -> str | None:
        """What a goal is, when it is not what it misses."""
        tl = self._tl
        if progress.ready:
            return tl("ready")
        if not progress.known:
            return tl("recipe unknown")
        if not progress.counted:
            return tl("conditions to meet in game")
        if progress.ready_alone and progress.missing is not None:
            return tl("taken by a goal above")
        return None

    def _alert_text(self) -> str | None:
        tl = self._tl
        match self._alert:
            case MaterialCapped(symbol=symbol, cap=cap):
                return tl("{material} at its cap ({cap})").format(
                    material=self._names.material(symbol), cap=self._number(cap, 0)
                )
            case GoalReady(goal=goal):
                return tl("Goal ready: {goal}").format(goal=self._names.goal(goal))
            case GoalDone(goal=goal):
                return tl("Goal done: {goal}").format(goal=self._names.goal(goal))
            case _:
                return None
