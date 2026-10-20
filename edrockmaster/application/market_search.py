"""Where to buy and where to sell a commodity (ADR 0040, ADR 0047), on the community sources
(ADR 0039): one search for the Mining and Trade tabs.

The sources are asked only when the player searches. Their offers are filtered by the
domain (``select_offers``), so that what the player sees does not depend on the source
that answered.
"""

from __future__ import annotations

from collections.abc import Callable

from edrockmaster.application.community import Answer, Found
from edrockmaster.application.ports import Clock, CommodityMarkets
from edrockmaster.domain.commodities import MarketOffer, MarketQuery, select_offers

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
