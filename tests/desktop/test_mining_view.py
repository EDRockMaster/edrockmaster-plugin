"""The Mining tab's forms and answers, without the core (ADR 0040)."""

from typing import Any

import pytest

from edrockmaster.application.community import Failed, Source, Unavailable
from edrockmaster.desktop.mining_view import (
    estimate_view,
    hotspot_query,
    hotspots_view,
    refused,
)
from edrockmaster.domain.mining.hotspots import ReserveLevel

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
    assert hotspots_view(Failed(Source.SPANSH, Unavailable.OFF), str)["rings"] == []
    estimate = estimate_view(failed, "Borann", str)
    assert (estimate["status"], estimate["system"], estimate["lines"]) == ("busy", "Borann", [])
    assert refused("hotspots", "invalid")["hasMore"] is False
