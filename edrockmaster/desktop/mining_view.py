"""The *Mining* tab (ADR 0040): what its forms ask, and what the sources answered.

``hotspot_query`` and ``sale_query`` turn a form into a query, refusing what is
not valid (``ValueError``); the ``*_view`` functions turn an answer into what
the interface shows, as ``schemas/mining.schema.json`` describes it. Names are
in the player's language; numbers and dates are left to the interface.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from edrockmaster.application.community import Answer, Failed, Found
from edrockmaster.application.settings import SourceSettings
from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.mining.hotspots import (
    HOTSPOT_COMMODITIES,
    HotspotPage,
    HotspotQuery,
    ReserveLevel,
    hotspot_commodity,
)
from edrockmaster.domain.mining.markets import CargoEstimate, MarketOffer, SaleQuery
from edrockmaster.domain.ships import PadSize
from edrockmaster.ui.commodity_names import commodity_name

type Translate = Callable[[str], str]

_PADS = {pad.name.lower(): pad for pad in PadSize}


def _date(moment: datetime | None) -> str | None:
    return moment.astimezone(UTC).isoformat() if moment is not None else None


def _name(key: str, translate: Translate) -> str:
    return commodity_name(Commodity.from_symbol(key), translate)


def _pad(pad: PadSize | None) -> str | None:
    return pad.name.lower() if pad is not None else None


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
        "pad": _pad(pad),
        "sources": {"spansh": sources.spansh, "ardent": sources.ardent},
    }


def _text(request: Mapping[str, Any], field: str) -> str:
    value = request.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: missing")
    return value


def _number(request: Mapping[str, Any], field: str) -> float:
    value = request.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field}: not a number")
    return float(value)


def _whole(request: Mapping[str, Any], field: str) -> int:
    value = request.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field}: not a whole number")
    return value


def hotspot_query(request: Mapping[str, Any]) -> HotspotQuery:
    commodity = hotspot_commodity(_text(request, "commodity"))
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
        _text(request, "system"),
        minimum_count=_whole(request, "minimumCount"),
        reserves=frozenset(level for level in levels if level is not None),
        max_distance=_number(request, "maxDistance"),
        page=_whole(request, "page"),
    )


def sale_query(request: Mapping[str, Any]) -> SaleQuery:
    pad = request.get("pad")
    if pad is not None and pad not in _PADS:
        raise ValueError(f"pad: not one of {sorted(_PADS)}")
    carriers = request.get("carriers")
    if not isinstance(carriers, bool):
        raise ValueError("carriers: not true or false")
    return SaleQuery(
        _text(request, "commodity"),
        _text(request, "system"),
        max_distance=_number(request, "maxDistance"),
        needed_pad=_PADS[pad] if pad is not None else None,
        carriers=carriers,
    )


def refresh(request: Mapping[str, Any]) -> bool:
    return request.get("refresh") is True


def _status[T](answer: Answer[T]) -> dict[str, Any]:
    if isinstance(answer, Failed):
        return {
            "status": answer.reason.value,
            "source": answer.source.value,
            "readAt": None,
            "unavailable": None,
        }
    return {
        "status": "found",
        "source": answer.source.value,
        "readAt": _date(answer.read_at),
        "unavailable": answer.unavailable.value if answer.unavailable else None,
    }


_EMPTY: dict[str, dict[str, Any]] = {
    "hotspots": {"total": 0, "hasMore": False, "rings": []},
    "buyers": {"offers": []},
    "estimate": {"system": None, "lines": [], "total": 0},
}


def refused(answer: str, reason: str) -> dict[str, Any]:
    """An empty ``answer`` (hotspots, buyers, estimate): a form the core refused (``invalid``),
    a question it could not ask (``noSystem``, ``empty``), or the sources' silence (``down``)."""
    return {"status": reason, "source": None, "readAt": None, "unavailable": None, **_EMPTY[answer]}


def hotspots_view(answer: Answer[HotspotPage], translate: Translate) -> dict[str, Any]:
    view = _status(answer)
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
                "seen": _date(ring.seen),
            }
            for ring in page.rings
        ],
    }


def _offer(offer: MarketOffer) -> dict[str, Any]:
    return {
        "station": offer.station,
        "system": offer.system,
        "stationType": offer.station_type,
        "pad": _pad(offer.pad),
        "arrival": offer.arrival,
        "price": offer.price,
        "demand": offer.demand,
        "distance": offer.distance,
        "updated": _date(offer.updated),
        "carrier": offer.is_carrier,
    }


def buyers_view(answer: Answer[tuple[MarketOffer, ...]]) -> dict[str, Any]:
    view = _status(answer)
    offers = answer.value if isinstance(answer, Found) else ()
    return {**view, "offers": [_offer(offer) for offer in offers]}


def estimate_view(
    answer: Answer[CargoEstimate], system: str, translate: Translate
) -> dict[str, Any]:
    view = _status(answer)
    if not isinstance(answer, Found):
        return {**view, "system": system, "lines": [], "total": 0}
    return {
        **view,
        "system": system,
        "lines": [
            {
                "commodity": line.commodity,
                "name": _name(line.commodity, translate),
                "tons": line.tons,
                "value": line.value,
                "offer": _offer(line.best) if line.best is not None else None,
            }
            for line in answer.value.lines
        ],
        "total": answer.value.total,
    }
