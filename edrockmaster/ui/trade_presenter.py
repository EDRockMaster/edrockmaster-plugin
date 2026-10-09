"""Trade presenter: trade notifications in, panel texts out (ADR 0014)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import assert_never

from edrockmaster.domain.trade.journal import Market
from edrockmaster.domain.trade.session import (
    GoodsTally,
    RouteStats,
    TradeEnded,
    TradeEndReason,
    TradeNotification,
    TradeStarted,
    TradeStats,
    TradeUpdated,
    TransferKind,
    TransferStats,
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

ROUTE_LABEL_LENGTH = 32
"""Station names can be long: beyond this, a route would widen its block. A route
too long names its destination only, then is cut."""

# English source strings, translated at render time
_TRANSFER_LABELS = {
    TransferKind.DEPOSIT: "Deposited: {commodity}",
    TransferKind.WITHDRAWAL: "Withdrawn: {commodity}",
}
_END_REASONS = {
    TradeEndReason.GAME_CLOSED: "game closed",
    TradeEndReason.DIED: "ship destroyed",
    TradeEndReason.MANUAL: "reset",
}


class TradePresenter:
    def __init__(
        self, translate: Translate = identity, format_number: NumberFormat = default_number_format
    ) -> None:
        self._tl = translate
        self._number = format_number
        self._running = False
        self._ended: TradeEndReason | None = None
        self._stats: TradeStats | None = None

    def apply(self, notifications: Iterable[TradeNotification]) -> PanelModel:
        for notification in notifications:
            self._apply(notification)
        return self.render()

    def render(self) -> PanelModel:
        lines = tuple(self._lines(self._stats)) if self._stats else ()
        return PanelModel(status=self._status(), lines=lines, alert=None, can_reset=self._running)

    def _apply(self, notification: TradeNotification) -> None:
        match notification:
            case TradeStarted():
                self._running, self._ended, self._stats = True, None, None
            case TradeUpdated(stats=stats):
                self._stats = stats
            case TradeEnded(reason=reason, stats=stats):
                self._running, self._ended, self._stats = False, reason, stats
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(notification)

    def _status(self) -> str:
        tl = self._tl
        if self._running:
            return tl("Trade")
        if self._ended is not None:
            return tl("Trade session ended: {reason}").format(reason=tl(_END_REASONS[self._ended]))
        return tl("No trade session")

    def _lines(self, stats: TradeStats) -> Iterable[StatLine]:
        tl = self._tl
        yield StatLine(tl("Flight time"), format_duration(stats.flight_time, tl))
        yield StatLine(tl("Profit"), self._credits(stats.profit))
        if stats.tons_sold:  # hauling to a carrier sells nothing: no empty rates
            yield from self._sales_lines(stats)
        if stats.losses:
            yield StatLine(tl("Losses"), self._credits(stats.losses))
        if stats.cargo.tons:
            yield StatLine(tl("Cargo bought"), self._tally(stats.cargo))
        yield from (self._route_line(route) for route in stats.routes)
        yield from (self._transfer_line(moved) for moved in stats.transfers)
        if stats.refined.tons:
            yield StatLine(tl("Refined commodities"), self._tally(stats.refined))
        if stats.other.tons:
            yield StatLine(tl("Other goods"), self._tally(stats.other))

    def _sales_lines(self, stats: TradeStats) -> Iterable[StatLine]:
        tl = self._tl
        if stats.flight_time:
            yield StatLine(tl("Profit per hour"), self._credits(stats.profit_per_hour))
        sold = self._tons(stats.tons_sold)
        if stats.flight_time:
            sold = tl("{tons}, {rate} t/h").format(
                tons=sold, rate=self._number(stats.tons_per_hour, 0)
            )
        yield StatLine(tl("Sold"), sold)

    def _route_line(self, route: RouteStats) -> StatLine:
        commodity = commodity_name(route.commodity, self._tl)
        destination = self._market(route.destination)
        label = self._tl("{commodity}: {origin} to {destination}").format(
            commodity=commodity, origin=self._market(route.origin), destination=destination
        )
        if len(label) > ROUTE_LABEL_LENGTH:
            label = self._tl("{commodity} to {destination}").format(
                commodity=commodity, destination=destination
            )
        value = self._tl("{tons}, {profit}, {per_ton}/t").format(
            tons=self._tons(route.tons),
            profit=self._credits(route.profit),
            per_ton=self._credits(route.profit_per_ton),
        )
        return StatLine(_shorten(label), value)

    def _transfer_line(self, moved: TransferStats) -> StatLine:
        """What moved to or from fleet carriers, and in how many transfers (ADR 0019)."""
        tl = self._tl
        label = tl(_TRANSFER_LABELS[moved.kind]).format(
            commodity=commodity_name(moved.commodity, tl)
        )
        tons = self._tons(moved.tons)
        if moved.transfers == 1:
            return StatLine(label, tl("{tons} (1 transfer)").format(tons=tons))
        value = tl("{tons} ({count} transfers)").format(tons=tons, count=moved.transfers)
        return StatLine(label, value)

    def _market(self, market: Market | None) -> str:
        if market is None:
            return "?"
        return market.station or self._tl("market {id}").format(id=market.market_id)

    def _tally(self, tally: GoodsTally) -> str:
        return self._tl("{tons}, {credits}").format(
            tons=self._tons(tally.tons), credits=self._credits(tally.credits)
        )

    def _tons(self, tons: int) -> str:
        return self._tl("{tons} t").format(tons=self._number(tons, 0))

    def _credits(self, credits: float) -> str:
        return format_credits(credits, self._tl, self._number)


def _shorten(label: str) -> str:
    if len(label) <= ROUTE_LABEL_LENGTH:
        return label
    return label[: ROUTE_LABEL_LENGTH - 1].rstrip() + "…"
