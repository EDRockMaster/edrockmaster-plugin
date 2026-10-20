"""Where to mine (ADR 0040), with a source that answers at once."""

from collections.abc import Callable
from datetime import UTC, datetime

from edrockmaster.application.community import Answer, Found, Source
from edrockmaster.application.mining_search import MiningSearch
from edrockmaster.domain.mining.hotspots import HotspotPage, HotspotQuery, hotspot_commodity

READ = datetime(2026, 10, 12, 9, 55, tzinfo=UTC)


class FakeCatalogue:
    def __init__(self) -> None:
        self.asked: list[tuple[HotspotQuery, bool]] = []

    def find_hotspots(
        self,
        query: HotspotQuery,
        on_answer: Callable[[Answer[HotspotPage]], None],
        *,
        refresh: bool = False,
    ) -> None:
        self.asked.append((query, refresh))
        on_answer(Found(HotspotPage(query, (), 0), Source.SPANSH, READ))


def test_hotspots_are_asked_of_the_catalogue() -> None:
    painite = hotspot_commodity("Painite")
    assert painite is not None
    catalogue = FakeCatalogue()
    answers: list[Answer[HotspotPage]] = []
    query = HotspotQuery(painite, "Borann")
    MiningSearch(catalogue).find_hotspots(query, answers.append, refresh=True)
    assert catalogue.asked == [(query, True)]
    assert isinstance(answers[0], Found)
