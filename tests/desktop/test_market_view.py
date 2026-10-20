"""Where to buy and sell, the forms and answers without the core (ADR 0040, ADR 0047)."""

from datetime import UTC, datetime
from typing import Any

import pytest

from edrockmaster.application.community import Failed, Found, Source, Unavailable
from edrockmaster.desktop.market_view import market_query, markets_refused, markets_view
from edrockmaster.domain.commodities import Side
from edrockmaster.domain.ships import PadSize

FORM = {
    "side": "buy",
    "commodity": "gold",
    "system": "Sol",
    "maxDistance": 80,
    "pad": None,
    "carriers": True,
    "minVolume": 720,
}


def test_a_market_form_becomes_a_query() -> None:
    query = market_query(FORM)
    assert (query.side, query.commodity, query.reference) == (Side.BUY, "gold", "Sol")
    assert (query.needed_pad, query.carriers, query.min_volume) == (None, True, 720)
    sale = market_query({**FORM, "side": "sell", "pad": "medium"})
    assert (sale.side, sale.needed_pad) == (Side.SELL, PadSize.MEDIUM)


@pytest.mark.parametrize(
    "change",
    [
        {"side": None},
        {"side": "steal"},
        {"pad": "huge"},
        {"carriers": "yes"},
        {"minVolume": None},
        {"minVolume": 2.5},
        {"minVolume": 0},
        {"system": ""},
        {"maxDistance": 0},
    ],
)
def test_a_market_form_not_valid_is_refused(change: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match=r"\w"):
        market_query({**FORM, **change})


def test_a_failed_source_gives_no_offer() -> None:
    assert markets_view(Failed(Source.ARDENT, Unavailable.BUSY)) == {
        "status": "busy",
        "source": "ardent",
        "readAt": None,
        "unavailable": None,
        "offers": [],
    }
    assert markets_refused("invalid") == {
        "status": "invalid",
        "source": None,
        "readAt": None,
        "unavailable": None,
        "offers": [],
    }


def test_dates_are_utc() -> None:
    paris = datetime.fromisoformat("2026-10-12T11:00:00+02:00")
    view = markets_view(Found((), Source.ARDENT, paris))
    assert view["readAt"] == datetime(2026, 10, 12, 9, 0, tzinfo=UTC).isoformat()
