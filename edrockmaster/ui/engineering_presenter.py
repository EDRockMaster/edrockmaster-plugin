"""Engineering presenter: engineering notifications in, panel texts out (ADR 0017).

The panel block sums up the collection: materials gained per category, used,
those at their cap, and the goals ready. Its alert is the last material that
reached its cap, goal ready or goal done, until the next change without one.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import assert_never

from edrockmaster.domain.engineering.catalogue import MaterialCategory
from edrockmaster.domain.engineering.session import (
    CollectionEnded,
    CollectionEndReason,
    CollectionStarted,
    EngineeringNotification,
    EngineeringStats,
    EngineeringUpdated,
    GoalDone,
    GoalProgressed,
    GoalReady,
    MaterialCapped,
)
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
        return self.render()

    def render(self) -> PanelModel:
        return PanelModel(
            status=self._status(),
            lines=tuple(self._lines(self._stats)) if self._stats else (),
            alert=self._alert_text(),
            can_reset=self._running,
        )

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
        if stats.goals:
            ready = tl("{ready} of {total}").format(ready=stats.goals_ready, total=len(stats.goals))
            if not stats.inventory_known:
                ready = tl("inventory unknown")
            yield StatLine(tl("Goals ready"), ready)

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
