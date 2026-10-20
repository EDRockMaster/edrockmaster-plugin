"""Spansh's trade routes, read from the answers recorded on 20 October 2026 (ADR 0047,
ADR 0057): the request sent, the job queued, then computed, then its result."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from edrockmaster.application.community import Pending, Source
from edrockmaster.domain.ships import PadSize
from edrockmaster.domain.trade.routes import HopCommodity, RouteQuery, RouteStation, TradeRoute
from edrockmaster.infrastructure.sources.spansh_routes import (
    RESULTS,
    ROUTE,
    ROUTE_MAX_AGE,
    SpanshRoutes,
    read_route_answer,
    route_form,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "sources"
JOB = "A847C390-CCBA-11F1-A196-CA1F9215DF0A"
QUERY = RouteQuery(
    "Sol",
    "Abraham Lincoln",
    cargo_capacity=720,
    credits=100_000_000,
    max_hop_distance=30,
    needed_pad=PadSize.LARGE,
)


def recorded(name: str) -> Any:
    return json.loads((FIXTURES / f"spansh-trade-route-{name}-2026-10-20.json").read_text())


def test_the_form_its_site_sends() -> None:
    assert route_form(QUERY) == {
        "max_hops": 3,
        "max_hop_distance": "30",
        "system": "Sol",
        "station": "Abraham Lincoln",
        "starting_capital": 100_000_000,
        "max_cargo": 720,
        "max_system_distance": 10_000_000,
        "max_price_age": 172_800,
        "requires_large_pad": 1,
        "allow_prohibited": 0,
        "allow_planetary": 0,
        "allow_player_owned": 0,
        "allow_restricted_access": 0,
        "unique": 0,
        "permit": 0,
    }
    medium = route_form(
        RouteQuery(
            "Sol",
            "Daedalus",
            cargo_capacity=8,
            credits=0,
            max_hop_distance=12.5,
            max_price_age=timedelta(hours=6),
            needed_pad=PadSize.MEDIUM,
            planetary=True,
            carriers=True,
        )
    )
    assert (medium["max_hop_distance"], medium["max_price_age"]) == ("12.5", 21_600)
    assert (medium["requires_large_pad"], medium["allow_planetary"]) == (0, 1)
    assert medium["allow_player_owned"] == 1


@pytest.mark.parametrize("name", ["queued-sol", "started-sol"])
def test_a_job_queued_or_started_is_pending(name: str) -> None:
    assert read_route_answer(recorded(name)) == Pending(Source.SPANSH, JOB)


def test_the_route_computed() -> None:
    route = read_route_answer(recorded("sol"))
    assert isinstance(route, TradeRoute)
    assert len(route.hops) == 3
    first = route.hops[0]
    assert first.source == RouteStation(
        "Abraham Lincoln", "Sol", 505, datetime.fromtimestamp(1792519884, UTC)
    )
    assert (first.destination.station, first.destination.system) == ("Finger Ring", "LHS 149")
    assert round(first.distance, 1) == 29.8
    assert first.commodities == (
        HopCommodity("Hydrogen Fuel", 720, buy_price=85, sell_price=120, profit=35),
    )
    assert first.profit == 25_200
    assert route.profit == 26_214_480  # Spansh's cumulative profit


def test_an_unknown_status_is_not_read() -> None:
    with pytest.raises(ValueError, match="error"):
        read_route_answer({"status": "error", "error": "Could not find starting station"})


class FakeSource:
    def __init__(self) -> None:
        self.asked: list[tuple[str, timedelta, bool]] = []

    def follow(
        self, request: str, fetch: Any, parse: Any, max_age: Any, on_answer: Any, **options: Any
    ) -> None:
        self.asked.append((request, max_age, options["refresh"]))
        on_answer(parse(fetch()))  # the cache aside: ``CommunitySource.follow``


class FakeClient:
    def __init__(self) -> None:
        self.sent: list[tuple[str, object]] = []

    def post_form(self, url: str, form: Any) -> Any:
        self.sent.append((url, form))
        return recorded("queued-sol")

    def get(self, url: str) -> Any:
        self.sent.append((url, None))
        return recorded("sol")


def test_planning_sends_the_form_then_following_reads_the_job() -> None:
    source, client = FakeSource(), FakeClient()
    routes = SpanshRoutes(source, client)  # type: ignore[arg-type]
    answers: list[object] = []
    routes.plan(QUERY, answers.append)
    routes.follow(QUERY, JOB, answers.append)
    assert client.sent == [
        (ROUTE, route_form(QUERY)),
        (f"{RESULTS}/{JOB}", None),
    ]
    # Both under the request's parameters; a job is followed past the cache
    [(planned, age, refresh), (followed, _, followed_refresh)] = source.asked
    assert planned == followed
    assert (age, refresh, followed_refresh) == (ROUTE_MAX_AGE, False, True)
    assert timedelta(minutes=15) == ROUTE_MAX_AGE
    assert answers[0] == Pending(Source.SPANSH, JOB)
    assert isinstance(answers[1], TradeRoute)


def test_the_cache_keeps_nothing_of_the_player(monkeypatch: pytest.MonkeyPatch) -> None:
    # ADR 0039: neither the credits nor the cargo capacity, in the key or in the answer kept
    source, client = FakeSource(), FakeClient()
    kept: list[Any] = []
    monkeypatch.setattr(
        source, "follow", lambda request, fetch, *args, **options: kept.append((request, fetch()))
    )
    routes = SpanshRoutes(source, client)  # type: ignore[arg-type]
    routes.plan(QUERY, print)
    routes.follow(QUERY, JOB, print)
    for request, answer in kept:
        assert "100000000" not in request
        assert "parameters" not in answer
    assert kept[0][0] == kept[1][0]


def test_a_job_s_name_is_quoted() -> None:
    client = FakeClient()
    SpanshRoutes(FakeSource(), client).follow(QUERY, "a/b", lambda _answer: None)  # type: ignore[arg-type]
    assert client.sent == [(f"{RESULTS}/a%2Fb", None)]
