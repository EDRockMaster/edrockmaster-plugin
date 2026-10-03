from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import pytest

from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.mining.journal import ContentLevel, LimpetKind
from edrockmaster.domain.mining.prospecting import CommodityAlert, CoreAlert, ProspectorAlertRaised
from edrockmaster.domain.mining.session import (
    EndReason,
    SaleRecorded,
    SessionEnded,
    SessionStarted,
    SessionStats,
    SessionUpdated,
)
from edrockmaster.ui.mining_presenter import MiningPresenter
from edrockmaster.ui.panel_model import PanelModel, StatLine

T0 = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
PAINITE = Commodity.from_symbol("painite", "Painite")
PLATINUM = Commodity.from_symbol("platinum")
OSMIUM = Commodity.from_symbol("osmium")


def stats(
    minutes: float = 30,
    tons: dict[Commodity, int] | None = None,
    prospected: int = 0,
    **changes: object,
) -> SessionStats:
    base = SessionStats(
        started_at=T0,
        active_duration=timedelta(minutes=minutes),
        tons_by_commodity=MappingProxyType(tons if tons is not None else {PAINITE: 20}),
        refinements=sum((tons or {PAINITE: 20}).values()),
        prospected_by_content=MappingProxyType({ContentLevel.HIGH: prospected}),
        cores_found=0,
        cores_cracked=0,
        limpets_launched=MappingProxyType(Counter()),
        ejected_tons=MappingProxyType({}),
        cargo_tons=None,
        limpets_on_board=None,
        sold_tons=MappingProxyType({}),
        credits_earned=0,
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def alert(*alerts: CommodityAlert | CoreAlert) -> ProspectorAlertRaised:
    return ProspectorAlertRaised(at=T0, alerts=alerts)


def value(model: PanelModel, label: str) -> str:
    [line] = [line for line in model.lines if line.label == label]
    return line.value


def labels(model: PanelModel) -> list[str]:
    return [line.label for line in model.lines]


@pytest.fixture
def presenter() -> MiningPresenter:
    return MiningPresenter()


# --- status -------------------------------------------------------------------------------


def test_nothing_to_show_before_any_session(presenter: MiningPresenter) -> None:
    model = presenter.render()
    assert model == PanelModel(status="No mining session", lines=(), alert=None, can_reset=False)


def test_running_session_shows_its_ring(presenter: MiningPresenter) -> None:
    model = presenter.apply([SessionStarted(T0, "Col 285", "Col 285 2 A Ring")])
    assert model.status == "Mining: Col 285 2 A Ring"
    assert model.can_reset


def test_running_session_without_a_known_ring(presenter: MiningPresenter) -> None:
    assert presenter.apply([SessionStarted(T0, None, None)]).status == "Mining"


@pytest.mark.parametrize(
    ("reason", "status"),
    [
        (EndReason.SUPERCRUISE, "Session ended: supercruise"),
        (EndReason.JUMP, "Session ended: jump"),
        (EndReason.DOCKED, "Session ended: docked"),
        (EndReason.GAME_CLOSED, "Session ended: game closed"),
        (EndReason.MANUAL, "Session ended: reset"),
    ],
)
def test_ended_session_keeps_its_statistics(
    presenter: MiningPresenter, reason: EndReason, status: str
) -> None:
    presenter.apply([SessionStarted(T0, None, None), SessionUpdated(stats())])
    model = presenter.apply([SessionEnded(T0, reason, stats(tons={PAINITE: 25}))])
    assert model.status == status
    assert not model.can_reset
    assert value(model, "Refined") == "25 t"


# --- statistics ---------------------------------------------------------------------------


def test_main_statistics(presenter: MiningPresenter) -> None:
    model = presenter.apply(
        [
            SessionStarted(T0, None, None),
            SessionUpdated(stats(minutes=90, tons={PAINITE: 40, PLATINUM: 5}, prospected=12)),
        ]
    )
    assert labels(model) == ["Active time", "Refined", "Rate", "Painite", "Platinum", "Prospected"]
    assert value(model, "Active time") == "1 h 30 min"
    assert value(model, "Refined") == "45 t"
    assert value(model, "Rate") == "30.0 t/h"
    assert value(model, "Painite") == "40 t"
    assert value(model, "Prospected") == "12"


def test_commodities_are_listed_by_tons_then_name(presenter: MiningPresenter) -> None:
    model = presenter.apply([SessionUpdated(stats(tons={PLATINUM: 3, OSMIUM: 3, PAINITE: 9}))])
    assert labels(model)[3:6] == ["Painite", "Osmium", "Platinum"]


def test_short_durations_are_shown_in_minutes(presenter: MiningPresenter) -> None:
    model = presenter.apply([SessionUpdated(stats(minutes=7.9))])
    assert value(model, "Active time") == "7 min"


def test_optional_statistics_appear_once_known(presenter: MiningPresenter) -> None:
    model = presenter.apply(
        [
            SessionUpdated(
                stats(
                    cores_found=2,
                    cores_cracked=1,
                    limpets_launched=MappingProxyType(
                        {LimpetKind.PROSPECTOR: 14, LimpetKind.COLLECTOR: 3}
                    ),
                    cargo_tons=96,
                    sold_tons=MappingProxyType({PAINITE: 20}),
                    credits_earned=12_500_000,
                )
            )
        ]
    )
    assert value(model, "Cores") == "2 found, 1 cracked"
    assert value(model, "Limpets") == "prospectors: 14, collectors: 3"
    assert value(model, "Cargo") == "96 t"
    assert value(model, "Sold") == "20 t, 12,500,000 CR"


def test_sales_after_the_session_update_its_statistics(presenter: MiningPresenter) -> None:
    presenter.apply([SessionEnded(T0, EndReason.DOCKED, stats())])
    sold = stats(sold_tons=MappingProxyType({PAINITE: 20}), credits_earned=1_000)
    model = presenter.apply([SaleRecorded(T0, PAINITE, 20, 1_000, sold)])
    assert value(model, "Sold") == "20 t, 1,000 CR"
    assert model.status == "Session ended: docked"


def test_numbers_use_the_given_format() -> None:
    presenter = MiningPresenter(format_number=lambda number, decimals: f"<{number:.{decimals}f}>")
    model = presenter.apply([SessionUpdated(stats(minutes=60, tons={PAINITE: 20}))])
    assert value(model, "Refined") == "<20> t"
    assert value(model, "Rate") == "<20.0> t/h"


def test_commodity_names_fall_back_to_our_catalogue(presenter: MiningPresenter) -> None:
    ltd = Commodity.from_symbol("$lowtemperaturediamond_name;")
    unknown = Commodity.from_symbol("$weirdrock_name;")
    model = presenter.apply([SessionUpdated(stats(tons={ltd: 2, unknown: 1}))])
    assert "Low Temperature Diamonds" in labels(model)
    assert "weirdrock" in labels(model)


# --- alerts -------------------------------------------------------------------------------


def test_alert_is_shown(presenter: MiningPresenter) -> None:
    model = presenter.apply(
        [
            SessionUpdated(stats(prospected=1)),
            alert(CoreAlert(PAINITE), CommodityAlert(PLATINUM, 32.5, 20.0)),
        ]
    )
    assert model.alert == "Core: Painite · Platinum 32.5 %"


def test_alert_stays_until_the_next_asteroid_is_prospected(presenter: MiningPresenter) -> None:
    presenter.apply([SessionUpdated(stats(prospected=1)), alert(CoreAlert(PAINITE))])
    assert presenter.apply([SessionUpdated(stats(prospected=1, cargo_tons=3))]).alert
    assert presenter.apply([SessionUpdated(stats(prospected=2))]).alert is None


def test_a_new_alert_replaces_the_previous_one(presenter: MiningPresenter) -> None:
    presenter.apply([SessionUpdated(stats(prospected=1)), alert(CoreAlert(PAINITE))])
    model = presenter.apply(
        [SessionUpdated(stats(prospected=2)), alert(CommodityAlert(PAINITE, 41.0, 25.0))]
    )
    assert model.alert == "Painite 41.0 %"


def test_alert_is_cleared_when_the_session_ends(presenter: MiningPresenter) -> None:
    presenter.apply([SessionUpdated(stats(prospected=1)), alert(CoreAlert(PAINITE))])
    assert presenter.apply([SessionEnded(T0, EndReason.DOCKED, stats())]).alert is None


# --- language -----------------------------------------------------------------------------


def test_render_rebuilds_every_text_in_the_current_language() -> None:
    language = {"value": "en"}

    def translate(text: str) -> str:
        return f"[{text}]" if language["value"] == "fr" else text

    presenter = MiningPresenter(translate=translate)
    presenter.apply([SessionStarted(T0, None, None), SessionUpdated(stats())])
    language["value"] = "fr"
    model = presenter.render()
    assert model.status == "[Mining]"
    assert labels(model)[0] == "[Active time]"
    assert StatLine("[Refined]", "[20 t]") in model.lines
