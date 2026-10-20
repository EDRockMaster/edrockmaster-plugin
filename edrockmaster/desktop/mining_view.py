"""The *Mining* tab (ADR 0040): what its forms ask, and what the sources answered.

``hotspot_query`` turns a form into a query, refusing what is not valid
(``ValueError``); the ``*_view`` functions turn an answer into what the interface
shows, as ``schemas/mining.schema.json`` describes it. Where to sell and the cargo's
worth are the market search's, shared with the Trade tab (``market_view.py``). Names are in
the player's language; numbers and dates are left to the interface.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from edrockmaster.application.community import Answer, Found
from edrockmaster.application.settings import SourceSettings
from edrockmaster.desktop.market_view import (
    date,
    not_asked,
    number,
    pad_name,
    status,
    text,
    whole,
)
from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.mining.hotspots import (
    HOTSPOT_COMMODITIES,
    HotspotPage,
    HotspotQuery,
    ReserveLevel,
    hotspot_commodity,
)
from edrockmaster.domain.ships import PadSize
from edrockmaster.ui.commodity_names import commodity_name

type Translate = Callable[[str], str]


def _name(key: str, translate: Translate) -> str:
    return commodity_name(Commodity.from_symbol(key), translate)


def options_view(
    system: str | None, pad: PadSize | None, sources: SourceSettings, translate: Translate
) -> dict[str, Any]:
    """What the forms start from: the commodities, the current system, the ship's pad."""
    return {
        "commodities": [
            {"commodity": commodity.key, "name": _name(commodity.key, translate)}
            for commodity in HOTSPOT_COMMODITIES
        ],
        "system": system,
        "pad": pad_name(pad),
        "sources": {"spansh": sources.spansh, "ardent": sources.ardent},
    }


def hotspot_query(request: Mapping[str, Any]) -> HotspotQuery:
    commodity = hotspot_commodity(text(request, "commodity"))
    if commodity is None:
        raise ValueError("commodity: has no hotspots")
    reserves = request.get("reserves", [])
    if not isinstance(reserves, list):
        raise ValueError("reserves: not a list")
    levels = {ReserveLevel.from_name(str(name)) for name in reserves}
    if None in levels:
        raise ValueError(f"reserves: unknown level in {reserves!r}")
    return HotspotQuery(
        commodity,
        text(request, "system"),
        minimum_count=whole(request, "minimumCount"),
        reserves=frozenset(level for level in levels if level is not None),
        max_distance=number(request, "maxDistance"),
        page=whole(request, "page"),
    )


def refused(reason: str) -> dict[str, Any]:
    """Hotspots the core did not ask (``market_view.not_asked``)."""
    return {**not_asked(reason), "total": 0, "hasMore": False, "rings": []}


def hotspots_view(answer: Answer[HotspotPage], translate: Translate) -> dict[str, Any]:
    view = status(answer)
    if not isinstance(answer, Found):
        return {**view, "total": 0, "hasMore": False, "rings": []}
    page = answer.value
    chosen = page.query.commodity
    return {
        **view,
        "total": page.total,
        "hasMore": page.has_more,
        "rings": [
            {
                "system": ring.system,
                "body": ring.body,
                "ring": ring.name,
                "ringType": ring.ring_type,
                "reserve": ring.reserve.value if ring.reserve else None,
                "count": ring.count(chosen),
                "others": [
                    {"commodity": key, "name": _name(key, translate), "count": count}
                    for key, count in ring.hotspots
                    if key != chosen.key
                ],
                "distance": ring.distance,
                "arrival": ring.arrival,
                "seen": date(ring.seen),
            }
            for ring in page.rings
        ],
    }
