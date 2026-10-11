"""The Mining tab's forms and answers, without the core (ADR 0040)."""

from datetime import UTC, datetime
from typing import Any

import pytest

from edrockmaster.application.community import Failed, Found, Source, Unavailable
from edrockmaster.desktop.mining_view import (
    buyers_view,
    estimate_view,
    hotspot_query,
    hotspots_view,
    refused,
    sale_query,
)
from edrockmaster.domain.mining.hotspots import ReserveLevel
from edrockmaster.domain.ships import PadSize

HOTSPOTS = {
    "commodity": "Low Temperature Diamonds",
    "system": "HIP 21991",
    "minimumCount": 1,
    "reserves": ["pristine"],
    "maxDistance": 30.5,
    "page": 1,
}


def test_a_hotspot_form_becomes_a_query() -> None:
    query = hotspot_query(HOTSPOTS)
    assert query.commodity.key == "lowtemperaturediamond"
    assert query.reserves == frozenset({ReserveLevel.PRISTINE})
    assert (query.reference, query.max_distance, query.page) == ("HIP 21991", 30.5, 1)


def test_a_sale_form_becomes_a_query() -> None:
    query = sale_query(
        {"commodity": "gold", "system": "Sol", "maxDistance": 80, "pad": None, "carriers": True}
    )
    assert (query.commodity, query.needed_pad, query.carriers) == ("gold", None, True)
    medium = sale_query(
        {
            "commodity": "gold",
            "system": "Sol",
            "maxDistance": 80,
            "pad": "medium",
            "carriers": False,
        }
    )
    assert medium.needed_pad is PadSize.MEDIUM


@pytest.mark.parametrize(
    "change",
    [
        {"system": " "},
        {"system": None},
        {"maxDistance": "far"},
        {"maxDistance": True},
        {"page": 1.5},
        {"reserves": "pristine"},
        {"minimumCount": 0},
    ],
)
def test_a_hotspot_form_not_valid_is_refused(change: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match=r"\w"):
        hotspot_query({**HOTSPOTS, **change})


def test_a_failed_source_gives_empty_answers() -> None:
    failed = Failed(Source.ARDENT, Unavailable.BUSY)
    assert buyers_view(failed) == {
        "status": "busy",
        "source": "ardent",
        "readAt": None,
        "unavailable": None,
        "offers": [],
    }
    assert hotspots_view(Failed(Source.SPANSH, Unavailable.OFF), str)["rings"] == []
    estimate = estimate_view(failed, "Borann", str)
    assert (estimate["status"], estimate["system"], estimate["lines"]) == ("busy", "Borann", [])
    assert refused("hotspots", "invalid")["hasMore"] is False


def test_dates_are_utc() -> None:
    paris = datetime.fromisoformat("2026-10-12T11:00:00+02:00")
    view = buyers_view(Found((), Source.ARDENT, paris))
    assert view["readAt"] == datetime(2026, 10, 12, 9, 0, tzinfo=UTC).isoformat()
