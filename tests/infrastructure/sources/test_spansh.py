"""Spansh's body search, read from an answer recorded on 11 October 2026 (ADR 0040)."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from edrockmaster.application.community import Answer, Found, Source
from edrockmaster.domain.mining.hotspots import (
    HotspotCommodity,
    HotspotPage,
    HotspotQuery,
    ReserveLevel,
    hotspot_commodity,
)
from edrockmaster.infrastructure.sources.spansh import (
    BODY_SEARCH,
    SpanshCatalogue,
    body_search,
    read_hotspots,
)

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "sources"
    / "spansh-bodies-search-painite-borann-2026-10-11.json"
)
logger = logging.getLogger("test.spansh")


def commodity(name: str) -> HotspotCommodity:
    found = hotspot_commodity(name)
    assert found is not None
    return found


PAINITE = commodity("Painite")
QUERY = HotspotQuery(
    PAINITE,
    "Borann",
    minimum_count=2,
    reserves=frozenset({ReserveLevel.MAJOR, ReserveLevel.PRISTINE}),
    max_distance=20,
)


def recorded() -> Any:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_the_search_its_site_sends() -> None:
    assert body_search(QUERY) == {
        "filters": {
            "ring_signals": [{"comparison": "<=>", "count": [2, 9999], "name": "Painite"}],
            "distance": {"min": "0", "max": "20"},
            "reserve_level": {"value": ["Pristine", "Major"]},
        },
        "sort": [{"distance": {"direction": "asc"}}],
        "size": 10,
        "page": 0,
        "reference_system": "Borann",
    }
    any_reserve = body_search(HotspotQuery(commodity("lowtemperaturediamond"), "Sol", page=2))
    assert "reserve_level" not in any_reserve["filters"]
    assert any_reserve["filters"]["ring_signals"][0]["name"] == "Low Temperature Diamonds"
    assert any_reserve["filters"]["distance"]["max"] == "50"
    assert any_reserve["page"] == 2


def test_the_recorded_answer_gives_the_rings_nearest_first() -> None:
    page, unknown = read_hotspots(recorded(), QUERY)
    assert unknown == set()  # every hotspot Spansh names is known
    assert page.total == 5
    assert not page.has_more
    assert [(ring.name, ring.count(PAINITE), round(ring.distance, 1)) for ring in page.rings] == [
        ("Borann A 2 A Ring", 10, 0.0),
        ("Fugeirs 2 A Ring", 4, 14.2),
        ("HIP 45096 B 7 A Ring", 4, 17.4),
        ("Gango A 4 A Ring", 7, 19.2),
        ("Onileut 3 A Ring", 5, 19.9),
    ]
    borann = page.rings[0]
    assert (borann.system, borann.body, borann.ring_type) == ("Borann", "Borann A 2", "Metal Rich")
    assert borann.reserve is ReserveLevel.PRISTINE
    assert borann.arrival == pytest.approx(901.72, abs=0.01)
    assert borann.count(commodity("Serendibite")) == 4
    assert borann.seen == datetime(2022, 6, 17, 1, 31, 28, tzinfo=UTC)


def test_without_the_signals_date_the_body_s_date_is_the_age() -> None:
    page, _ = read_hotspots(recorded(), QUERY)
    hip = next(ring for ring in page.rings if ring.body == "HIP 45096 B 7")
    assert hip.seen == datetime(2026, 9, 7, 16, 25, 44, tzinfo=UTC)


def test_rings_without_enough_hotspots_and_unknown_signals_are_left_out() -> None:
    answer = recorded()
    borann = answer["results"][0]
    borann["rings"].append(
        {"name": "Borann A 2 B Ring", "type": "Icy", "signals": [{"name": "Painite", "count": 1}]}
    )
    borann["rings"][0]["signals"].append({"name": "Unobtainium", "count": 2})
    page, unknown = read_hotspots(answer, QUERY)
    assert [ring.name for ring in page.rings if ring.body == "Borann A 2"] == ["Borann A 2 A Ring"]
    assert unknown == {"Unobtainium"}


class FakeSource:
    def __init__(self) -> None:
        self.asked: list[tuple[str, Any]] = []

    def ask(
        self, request: str, fetch: Any, parse: Any, max_age: Any, on_answer: Any, **_: Any
    ) -> None:
        on_answer(Found(parse(fetch()), Source.SPANSH, datetime(2026, 10, 11, tzinfo=UTC)))


class FakeClient:
    def __init__(self, answer: Any) -> None:
        self.answer = answer
        self.posts: list[tuple[str, Any]] = []

    def post(self, url: str, body: Any) -> Any:
        self.posts.append((url, body))
        return self.answer


def test_the_catalogue_posts_the_search_and_reads_the_answer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    answer = recorded()
    answer["results"][0]["rings"][0]["signals"].append({"name": "Unobtainium", "count": 2})
    client = FakeClient(answer)
    answers: list[Answer[HotspotPage]] = []
    catalogue = SpanshCatalogue(FakeSource(), client, logger)  # type: ignore[arg-type]
    catalogue.find_hotspots(QUERY, answers.append)
    assert client.posts == [(BODY_SEARCH, body_search(QUERY))]
    [found] = answers
    assert isinstance(found, Found)
    assert len(found.value.rings) == 5
    assert "Unobtainium" in caplog.text
