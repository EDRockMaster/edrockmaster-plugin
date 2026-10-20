"""Where to mine, and what the mining cargo is worth (ADR 0040), on the community sources
(ADR 0039). Where to sell is the market search's (``market_search.py``), shared with the
Trade tab.

The sources are asked only when the player searches or asks for an estimate.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from edrockmaster.application.community import Answer, Failed, Found
from edrockmaster.application.market_search import MarketSearch, Offers
from edrockmaster.application.ports import GalaxyCatalogue
from edrockmaster.domain.commodities import MarketQuery, Side
from edrockmaster.domain.mining.hotspots import HotspotPage, HotspotQuery
from edrockmaster.domain.mining.markets import CargoEstimate, CargoLine
from edrockmaster.domain.ships import PadSize


class MiningSearch:
    def __init__(self, catalogue: GalaxyCatalogue, markets: MarketSearch) -> None:
        self._catalogue = catalogue
        self._markets = markets

    def find_hotspots(
        self,
        query: HotspotQuery,
        on_answer: Callable[[Answer[HotspotPage]], None],
        *,
        refresh: bool = False,
    ) -> None:
        self._catalogue.find_hotspots(query, on_answer, refresh=refresh)

    def estimate_cargo(
        self,
        cargo: Mapping[str, int],
        reference: str,
        needed_pad: PadSize | None,
        on_answer: Callable[[Answer[CargoEstimate]], None],
    ) -> None:
        """The cargo (tons by commodity key) at the best market around ``reference``.

        One search per commodity; the answer comes once all have answered, read at the
        time of the oldest, and says why when some could not be priced. An empty cargo
        has nothing to estimate: ``ValueError``.
        """
        tons = {commodity: count for commodity, count in sorted(cargo.items()) if count > 0}
        if not tons:
            raise ValueError("no cargo to estimate")
        answers: dict[str, Answer[Offers]] = {}

        def collect(commodity: str) -> Callable[[Answer[Offers]], None]:
            def collected(answer: Answer[Offers]) -> None:
                answers[commodity] = answer
                if len(answers) == len(tons):
                    on_answer(_estimate(tons, answers))

            return collected

        for commodity in tons:
            self._markets.find_offers(
                MarketQuery(Side.SELL, commodity, reference, needed_pad=needed_pad),
                collect(commodity),
            )


def _estimate(
    tons: Mapping[str, int], answers: Mapping[str, Answer[Offers]]
) -> Answer[CargoEstimate]:
    found = [answer for answer in answers.values() if isinstance(answer, Found)]
    failed = [answer for answer in answers.values() if isinstance(answer, Failed)]
    if not found:
        return failed[0]
    lines = tuple(
        CargoLine(
            commodity,
            count,
            answer.value[0] if isinstance(answer, Found) and answer.value else None,
        )
        for commodity, count in tons.items()
        for answer in (answers[commodity],)
    )
    unavailable = next(
        (answer.reason for answer in failed),
        next((answer.unavailable for answer in found if answer.unavailable), None),
    )
    oldest = min(found, key=lambda answer: answer.read_at)
    return Found(CargoEstimate(lines), oldest.source, oldest.read_at, unavailable)
