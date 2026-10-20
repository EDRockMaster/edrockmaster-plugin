"""Where to buy and where to sell a commodity (ADR 0040, ADR 0047), on the community sources
(ADR 0039): one search for the Mining and Trade tabs, which also estimates a cargo at the best
markets; and the galaxy's prices of a commodity, to judge an offer.

The sources are asked only when the player searches or asks for an estimate. Their offers
are filtered by the domain (``select_offers``), so that what the player sees does not depend
on the source that answered.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from edrockmaster.application.community import Answer, Failed, Found
from edrockmaster.application.ports import Clock, CommodityMarkets
from edrockmaster.domain.commodities import (
    CargoEstimate,
    CargoLine,
    GalaxyPrices,
    MarketOffer,
    MarketQuery,
    Side,
    select_offers,
)
from edrockmaster.domain.ships import PadSize

type Offers = tuple[MarketOffer, ...]


class MarketSearch:
    def __init__(self, markets: CommodityMarkets, clock: Clock) -> None:
        self._markets = markets
        self._clock = clock

    def find_offers(
        self,
        query: MarketQuery,
        on_answer: Callable[[Answer[Offers]], None],
        *,
        refresh: bool = False,
    ) -> None:
        """The markets the query accepts, the best price first."""

        def selected(answer: Answer[Offers]) -> None:
            if isinstance(answer, Found):
                offers = select_offers(answer.value, query, self._clock.now())
                answer = Found(offers, answer.source, answer.read_at, answer.unavailable)
            on_answer(answer)

        self._markets.find_offers(query, selected, refresh=refresh)

    def find_galaxy_prices(
        self,
        on_answer: Callable[[Answer[Mapping[str, GalaxyPrices]]], None],
        *,
        refresh: bool = False,
    ) -> None:
        """Every commodity's prices across the galaxy, by key: one answer for all."""
        self._markets.find_prices(on_answer, refresh=refresh)

    def find_prices(
        self,
        commodity: str,
        on_answer: Callable[[Answer[GalaxyPrices | None]], None],
        *,
        refresh: bool = False,
    ) -> None:
        """The commodity's prices across the galaxy; ``None`` when the source does not know
        it."""
        key = commodity.strip().lower()

        def picked(answer: Answer[Mapping[str, GalaxyPrices]]) -> None:
            if isinstance(answer, Found):
                on_answer(
                    Found(answer.value.get(key), answer.source, answer.read_at, answer.unavailable)
                )
            else:
                on_answer(answer)

        self.find_galaxy_prices(picked, refresh=refresh)

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
            self.find_offers(
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
