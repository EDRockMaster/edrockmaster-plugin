"""Spansh, as a ``GalaxyCatalogue`` (ADR 0039, ADR 0040).

Spansh publishes no documentation of its API: the body search below is the
request its own site sends. The answer recorded in ``tests/fixtures/sources/``
is the contract this adapter relies on.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

from edrockmaster.application.community import Answer
from edrockmaster.domain.mining.hotspots import (
    PAGE_SIZE,
    HotspotPage,
    HotspotQuery,
    ReserveLevel,
    Ring,
    hotspot_commodity,
)
from edrockmaster.infrastructure.sources.http import SourceClient
from edrockmaster.infrastructure.sources.source import CommunitySource

BODY_SEARCH = "https://spansh.co.uk/api/bodies/search"
HOTSPOTS_MAX_AGE = timedelta(days=1)
_MOST_HOTSPOTS = 9999


def body_search(query: HotspotQuery) -> dict[str, Any]:
    """Spansh's search for the bodies with a ring holding the query's hotspots."""
    filters: dict[str, Any] = {
        "ring_signals": [
            {
                "comparison": "<=>",
                "count": [query.minimum_count, _MOST_HOTSPOTS],
                "name": query.commodity.english,
            }
        ],
        "distance": {"min": "0", "max": f"{query.max_distance:g}"},
    }
    if query.reserves:
        ordered = [level for level in ReserveLevel if level in query.reserves]
        filters["reserve_level"] = {"value": [level.value.capitalize() for level in ordered]}
    return {
        "filters": filters,
        "sort": [{"distance": {"direction": "asc"}}],
        "size": PAGE_SIZE,
        "page": query.page,
        "reference_system": query.reference,
    }


def _date(value: Any) -> datetime | None:
    return datetime.fromisoformat(str(value)) if value else None


def read_hotspots(answer: Mapping[str, Any], query: HotspotQuery) -> tuple[HotspotPage, set[str]]:
    """The rings of the answer with the query's hotspots, and the signal names not known."""
    unknown: set[str] = set()
    rings: list[Ring] = []
    for body in answer["results"]:
        seen = _date(body.get("signals_updated_at") or body.get("updated_at"))
        for ring in body.get("rings") or ():
            hotspots: dict[str, int] = {}
            for signal in ring.get("signals") or ():
                commodity = hotspot_commodity(str(signal["name"]))
                if commodity is None:
                    unknown.add(str(signal["name"]))
                    continue
                hotspots[commodity.key] = int(signal["count"])
            if hotspots.get(query.commodity.key, 0) < query.minimum_count:
                continue
            rings.append(
                Ring(
                    system=str(body["system_name"]),
                    body=str(body["name"]),
                    name=str(ring["name"]),
                    ring_type=str(ring["type"]),
                    reserve=ReserveLevel.from_name(body.get("reserve_level")),
                    hotspots=tuple(hotspots.items()),
                    distance=float(body["distance"]),
                    arrival=body.get("distance_to_arrival"),
                    seen=seen,
                )
            )
    return HotspotPage(query, tuple(rings), int(answer["count"])), unknown


class SpanshCatalogue:
    def __init__(
        self, source: CommunitySource, client: SourceClient, logger: logging.Logger
    ) -> None:
        self._source = source
        self._client = client
        self._logger = logger

    def find_hotspots(
        self,
        query: HotspotQuery,
        on_answer: Callable[[Answer[HotspotPage]], None],
        *,
        refresh: bool = False,
    ) -> None:
        request = body_search(query)

        def parse(answer: Any) -> HotspotPage:
            page, unknown = read_hotspots(answer, query)
            if unknown:
                self._logger.warning("Spansh names hotspots not known: %s", sorted(unknown))
            return page

        self._source.ask(
            json.dumps(request, sort_keys=True),
            lambda: self._client.post(BODY_SEARCH, request),
            parse,
            HOTSPOTS_MAX_AGE,
            on_answer,
            refresh=refresh,
        )
