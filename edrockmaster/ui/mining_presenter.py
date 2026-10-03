"""Mining presenter: mining notifications in, panel texts out."""

from __future__ import annotations

from collections.abc import Iterable
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

# English source strings, translated at render time; listed here so that every
# displayed text can be found in one place.
_END_REASONS = {
    EndReason.SUPERCRUISE: "supercruise",
    EndReason.JUMP: "jump",
    EndReason.DOCKED: "docked",
    EndReason.GAME_CLOSED: "game closed",
    EndReason.MANUAL: "reset",
}


class MiningPresenter:
    def __init__(
        self,
        translate: Translate = identity,
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
            StatLine(tl("Active time"), format_duration(stats.active_duration, tl)),
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
            sold = tl("{tons}, {credits}").format(
                tons=self._tons(sum(stats.sold_tons.values())),
                credits=format_credits(stats.credits_earned, tl, number),
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

    def _tons(self, tons: int) -> str:
        return self._tl("{tons} t").format(tons=self._number(tons, 0))

    def _name(self, commodity: Commodity) -> str:
        return commodity_name(commodity, self._tl)
