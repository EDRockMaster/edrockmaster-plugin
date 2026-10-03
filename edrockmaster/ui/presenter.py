"""Presenter of the main window panel: notifications in, displayable texts out.

Pure Python, no tkinter: the panel only copies the texts of ``PanelModel``.
The presenter keeps domain objects, not texts, so that ``render()`` rebuilds
everything in the current language after the player changes it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import assert_never

from edrockmaster.application.mining_service import MiningNotification
from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.mining.journal import LimpetKind
from edrockmaster.domain.mining.prospecting import CommodityAlert, CoreAlert, ProspectorAlertRaised
from edrockmaster.domain.mining.session import (
    EndReason,
    SaleRecorded,
    SessionEnded,
    SessionStarted,
    SessionStats,
    SessionUpdated,
)
from edrockmaster.ui.commodity_names import commodity_name

type NumberFormat = Callable[[float, int], str]
"""Formats a number with the given count of decimals."""


def default_number_format(number: float, decimals: int) -> str:
    return f"{number:,.{decimals}f}"


def _identity(text: str) -> str:
    return text


# English source strings, translated at render time; listed here so that every
# displayed text can be found in one place.
_END_REASONS = {
    EndReason.SUPERCRUISE: "supercruise",
    EndReason.JUMP: "jump",
    EndReason.DOCKED: "docked",
    EndReason.GAME_CLOSED: "game closed",
    EndReason.MANUAL: "reset",
}


@dataclass(frozen=True, slots=True)
class StatLine:
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class PanelModel:
    status: str
    lines: tuple[StatLine, ...]
    alert: str | None
    can_reset: bool


class Presenter:
    def __init__(
        self,
        translate: Callable[[str], str] = _identity,
        format_number: NumberFormat = default_number_format,
    ) -> None:
        self._tl = translate
        self._number = format_number
        self._running = False
        self._ring: str | None = None
        self._ended: EndReason | None = None
        self._stats: SessionStats | None = None
        self._alert: ProspectorAlertRaised | None = None

    def apply(self, notifications: Iterable[MiningNotification]) -> PanelModel:
        for notification in notifications:
            self._apply(notification)
        return self.render()

    def render(self) -> PanelModel:
        return PanelModel(
            status=self._status(),
            lines=self._lines(self._stats) if self._stats else (),
            alert=self._alert_text(self._alert) if self._alert else None,
            can_reset=self._running,
        )

    # --- state ----------------------------------------------------------------------------

    def _apply(self, notification: MiningNotification) -> None:
        match notification:
            case SessionStarted(ring=ring):
                self._running, self._ring, self._ended = True, ring, None
                self._stats = self._alert = None
            case SessionUpdated(stats=stats):
                previous = self._stats
                if previous is None or stats.prospected_total > previous.prospected_total:
                    self._alert = None  # a new asteroid: the previous alert is stale
                self._stats = stats
            case ProspectorAlertRaised():
                self._alert = notification
            case SessionEnded(reason=reason, stats=stats):
                self._running, self._ended = False, reason
                self._stats, self._alert = stats, None
            case SaleRecorded(stats=stats):
                self._stats = stats
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(notification)

    # --- texts ----------------------------------------------------------------------------

    def _status(self) -> str:
        tl = self._tl
        if self._running:
            return tl("Mining: {ring}").format(ring=self._ring) if self._ring else tl("Mining")
        if self._ended is not None:
            return tl("Session ended: {reason}").format(reason=tl(_END_REASONS[self._ended]))
        return tl("No mining session")

    def _lines(self, stats: SessionStats) -> tuple[StatLine, ...]:
        tl, number = self._tl, self._number
        lines = [
            StatLine(tl("Active time"), self._duration(stats)),
            StatLine(tl("Refined"), self._tons(stats.total_tons)),
            StatLine(tl("Rate"), tl("{rate} t/h").format(rate=number(stats.tons_per_hour, 1))),
        ]
        lines += [
            StatLine(self._name(commodity), self._tons(tons))
            for commodity, tons in sorted(
                stats.tons_by_commodity.items(), key=lambda item: (-item[1], self._name(item[0]))
            )
        ]
        lines.append(StatLine(tl("Prospected"), number(stats.prospected_total, 0)))
        if stats.cores_found or stats.cores_cracked:
            cores = tl("{found} found, {cracked} cracked").format(
                found=number(stats.cores_found, 0), cracked=number(stats.cores_cracked, 0)
            )
            lines.append(StatLine(tl("Cores"), cores))
        if stats.limpets_launched:
            limpets = tl("prospectors: {prospectors}, collectors: {collectors}").format(
                prospectors=number(stats.limpets_launched.get(LimpetKind.PROSPECTOR, 0), 0),
                collectors=number(stats.limpets_launched.get(LimpetKind.COLLECTOR, 0), 0),
            )
            lines.append(StatLine(tl("Limpets"), limpets))
        if stats.cargo_tons is not None:
            lines.append(StatLine(tl("Cargo"), self._tons(stats.cargo_tons)))
        if stats.credits_earned:
            sold = tl("{tons}, {credits} CR").format(
                tons=self._tons(sum(stats.sold_tons.values())),
                credits=number(stats.credits_earned, 0),
            )
            lines.append(StatLine(tl("Sold"), sold))
        return tuple(lines)

    def _alert_text(self, raised: ProspectorAlertRaised) -> str:
        parts = []
        for alert in raised.alerts:
            match alert:
                case CoreAlert(commodity=commodity):
                    parts.append(
                        self._tl("Core: {commodity}").format(commodity=self._name(commodity))
                    )
                case CommodityAlert(commodity=commodity, proportion=proportion):
                    parts.append(f"{self._name(commodity)} {self._number(proportion, 1)} %")
                case _:  # pragma: no cover - exhaustiveness checked by mypy
                    assert_never(alert)
        return " · ".join(parts)

    def _duration(self, stats: SessionStats) -> str:
        minutes = int(stats.active_duration.total_seconds() // 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return self._tl("{hours} h {minutes} min").format(hours=hours, minutes=f"{minutes:02d}")
        return self._tl("{minutes} min").format(minutes=minutes)

    def _tons(self, tons: int) -> str:
        return self._tl("{tons} t").format(tons=self._number(tons, 0))

    def _name(self, commodity: Commodity) -> str:
        return commodity_name(commodity, self._tl)
