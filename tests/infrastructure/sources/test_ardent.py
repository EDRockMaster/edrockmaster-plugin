"""Ardent's nearby importers, read from an answer recorded on 11 October 2026 (ADR 0040)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from edrockmaster.application.community import Answer, Found, Source
from edrockmaster.domain.mining.markets import MarketOffer, SaleQuery
from edrockmaster.domain.ships import PadSize
from edrockmaster.infrastructure.sources.ardent import ArdentMarkets, nearby_imports, read_offers

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "sources"
    / "ardent-nearby-imports-painite-borann-2026-10-11.json"
)


def recorded() -> Any:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_the_address_of_the_nearby_importers() -> None:
    assert nearby_imports(SaleQuery("painite", "Borann", max_distance=20.5)) == (
        "https://api.ardent-insight.com/v2/system/name/Borann/commodity/name/painite/"
        "nearby/imports?maxDistance=21&maxDaysAgo=30&minVolume=1&fleetCarriers=false"
    )
    with_carriers = nearby_imports(
        SaleQuery("lowtemperaturediamond", "HIP 21991", carriers=True, max_age=timedelta(hours=6))
    )
    assert with_carriers == (
        "https://api.ardent-insight.com/v2/system/name/HIP%2021991/commodity/name/"
        "lowtemperaturediamond/nearby/imports?maxDistance=50&maxDaysAgo=1&minVolume=1"
    )


def test_the_recorded_answer_gives_the_offers() -> None:
    offers = read_offers(recorded())
    assert len(offers) == 6
    first = offers[0]
    assert first == MarketOffer(
        station="Borisenko's Folly",
        system="Arouca",
        market_id=3539221504,
        station_type="CraterPort",
        pad=PadSize.LARGE,
        arrival=83.874867,
        price=91254,
        demand=95,
        distance=20.0,
        updated=datetime(2026, 10, 11, 10, 11, 18, tzinfo=UTC),
        is_carrier=False,
    )
    assert offers[3].pad is PadSize.MEDIUM
    carrier = offers[-1]
    assert (carrier.station, carrier.is_carrier, carrier.price) == ("ABC-123", True, 300459)


class FakeSource:
    def ask(
        self, request: str, fetch: Any, parse: Any, max_age: Any, on_answer: Any, **_: Any
    ) -> None:
        on_answer(Found(parse(fetch()), Source.ARDENT, datetime(2026, 10, 11, tzinfo=UTC)))


class FakeClient:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get(self, url: str) -> Any:
        self.urls.append(url)
        return recorded()


def test_the_markets_get_the_address_and_read_the_answer() -> None:
    client = FakeClient()
    answers: list[Answer[tuple[MarketOffer, ...]]] = []
    query = SaleQuery("painite", "Borann")
    ArdentMarkets(FakeSource(), client).find_buyers(query, answers.append)  # type: ignore[arg-type]
    assert client.urls == [nearby_imports(query)]
    [found] = answers
    assert isinstance(found, Found)
    assert len(found.value) == 6
