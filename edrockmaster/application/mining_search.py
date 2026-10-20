"""Where to mine (ADR 0040), on the community sources (ADR 0039): asked only when the player
searches. Where to sell and the cargo's worth are the market search's (``market_search.py``),
shared with the Trade tab.
"""

from __future__ import annotations

from collections.abc import Callable

from edrockmaster.application.community import Answer
from edrockmaster.application.ports import GalaxyCatalogue
from edrockmaster.domain.mining.hotspots import HotspotPage, HotspotQuery


class MiningSearch:
    def __init__(self, catalogue: GalaxyCatalogue) -> None:
        self._catalogue = catalogue

    def find_hotspots(
        self,
        query: HotspotQuery,
        on_answer: Callable[[Answer[HotspotPage]], None],
        *,
        refresh: bool = False,
    ) -> None:
        self._catalogue.find_hotspots(query, on_answer, refresh=refresh)
