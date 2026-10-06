from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.trade.journal import Market
from edrockmaster.domain.trade.session import (
    GoodsTally,
    RouteStats,
    TradeEnded,
    TradeEndReason,
    TradeStarted,
    TradeStats,
    TradeUpdated,
)
from edrockmaster.ui.trade_presenter import ROUTE_LABEL_LENGTH, TradePresenter

T0 = datetime(2026, 10, 4, 14, 24, tzinfo=UTC)
AMANO = Market(1, "Amano Terminal")
VERNE = Market(2, "Verne Venture")
PALLADIUM = Commodity("palladium")
CMM = Commodity("cmmcomposite", "Composite MMC")
NONE = GoodsTally()


def route(
    commodity: Commodity = PALLADIUM,
    origin: Market | None = AMANO,
    destination: Market = VERNE,
    tons: int = 100,
    profit: int = 4_500_000,
) -> RouteStats:
    return RouteStats(commodity, origin, destination, tons, profit, 1)


def stats(
    *routes: RouteStats,
    flight: timedelta = timedelta(minutes=30),
    losses: int = 0,
    refined: GoodsTally = NONE,
    other: GoodsTally = NONE,
    cargo: GoodsTally = NONE,
) -> TradeStats:
    return TradeStats(T0, flight, routes, losses, refined, other, cargo)


def lines(presenter: TradePresenter) -> dict[str, str]:
    return {line.label: line.value for line in presenter.render().lines}


def test_no_session() -> None:
    model = TradePresenter().render()
    assert (model.status, model.lines, model.can_reset) == ("No trade session", (), False)


def test_running_session() -> None:
    presenter = TradePresenter()
    model = presenter.apply(
        [TradeStarted(T0), TradeUpdated(stats(route(), cargo=GoodsTally(1040, 5_602_480)))]
    )
    assert (model.status, model.can_reset) == ("Trade", True)
    assert lines(presenter) == {
        "Flight time": "30 min",
        "Profit": "4,500,000 CR",
        "Profit per hour": "9,000,000 CR",
        "Sold": "100 t, 200 t/h",
        "Cargo bought": "1,040 t, 5,602,480 CR",
        "Palladium to Verne Venture": "100 t, 4,500,000 CR, 45,000 CR/t",
    }


def test_a_route_too_long_names_its_destination_only() -> None:
    presenter = TradePresenter()
    presenter.apply([TradeStarted(T0), TradeUpdated(stats(route(CMM, VERNE, AMANO)))])
    assert "Composite MMC to Amano Terminal" in lines(presenter)


def test_a_destination_too_long_is_cut() -> None:
    presenter = TradePresenter()
    far = Market(5, "Jameson Memorial Orbital Starport")
    presenter.apply([TradeStarted(T0), TradeUpdated(stats(route(destination=far)))])
    [label] = [label for label in lines(presenter) if label.startswith("Palladium")]
    assert label == "Palladium to Jameson Memorial O…"
    assert len(label) == ROUTE_LABEL_LENGTH


def test_a_short_route_names_both_markets() -> None:
    presenter = TradePresenter()
    short = route(origin=Market(3, "Ohm"), destination=Market(4, "Volta"))
    presenter.apply([TradeStarted(T0), TradeUpdated(stats(short))])
    assert "Palladium: Ohm to Volta" in lines(presenter)


def test_unknown_and_unnamed_markets() -> None:
    presenter = TradePresenter()
    presenter.apply(
        [TradeStarted(T0), TradeUpdated(stats(route(origin=None, destination=Market(7))))]
    )
    assert "Palladium: ? to market 7" in lines(presenter)


def test_no_rate_before_any_flight() -> None:
    presenter = TradePresenter()
    presenter.apply([TradeStarted(T0), TradeUpdated(stats(route(), flight=timedelta(0)))])
    shown = lines(presenter)
    assert "Profit per hour" not in shown
    assert shown["Sold"] == "100 t"


def test_losses_refined_commodities_and_other_goods() -> None:
    presenter = TradePresenter()
    presenter.apply(
        [
            TradeStarted(T0),
            TradeUpdated(
                stats(
                    route(),
                    losses=50_000,
                    refined=GoodsTally(10, 3_000_000),
                    other=GoodsTally(2, 20_000),
                )
            ),
        ]
    )
    shown = lines(presenter)
    assert shown["Losses"] == "50,000 CR"
    assert shown["Refined commodities"] == "10 t, 3,000,000 CR"
    assert shown["Other goods"] == "2 t, 20,000 CR"
    assert list(shown)[-2:] == ["Refined commodities", "Other goods"]


@pytest.mark.parametrize(
    ("reason", "text"),
    [
        (TradeEndReason.GAME_CLOSED, "game closed"),
        (TradeEndReason.DIED, "ship destroyed"),
        (TradeEndReason.MANUAL, "reset"),
    ],
)
def test_ended_session_keeps_its_figures(reason: TradeEndReason, text: str) -> None:
    presenter = TradePresenter()
    model = presenter.apply([TradeStarted(T0), TradeEnded(T0, reason, stats(route()))])
    assert model.status == f"Trade session ended: {text}"
    assert not model.can_reset
    assert lines(presenter)["Profit"] == "4,500,000 CR"


def test_texts_are_translated() -> None:
    presenter = TradePresenter(translate=lambda text: "fr:" + text)
    model = presenter.apply([TradeStarted(T0), TradeUpdated(stats(route()))])
    assert model.status == "fr:Trade"
    assert model.lines[0].label == "fr:Flight time"
