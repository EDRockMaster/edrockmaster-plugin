"""Where to buy and where to sell, and a cargo's worth, for the Mining and Trade tabs (ADR 0040,
ADR 0047).

``market_query`` turns a form into a query, refusing what is not valid
(``ValueError``); ``markets_view`` and ``estimate_view`` turn an answer into what the
interface shows, as ``schemas/markets.schema.json`` describes it. The helpers below serve the other
answers of the sources too (``mining_view.py``, ``trade_view.py``). Numbers and dates
are left to the interface.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from edrockmaster.application.community import Answer, Failed, Found
from edrockmaster.domain.commodities import CargoEstimate, MarketOffer, MarketQuery, Side
from edrockmaster.domain.ships import PadSize

_PADS = {pad.name.lower(): pad for pad in PadSize}
_SIDES = {side.value: side for side in Side}


def date(moment: datetime | None) -> str | None:
    return moment.astimezone(UTC).isoformat() if moment is not None else None


def pad_name(pad: PadSize | None) -> str | None:
    return pad.name.lower() if pad is not None else None


def text(request: Mapping[str, Any], field: str) -> str:
    value = request.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: missing")
    return value


def number(request: Mapping[str, Any], field: str) -> float:
    value = request.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field}: not a number")
    return float(value)


def whole(request: Mapping[str, Any], field: str) -> int:
    value = request.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field}: not a whole number")
    return value


def refresh(request: Mapping[str, Any]) -> bool:
    return request.get("refresh") is True


def market_query(request: Mapping[str, Any]) -> MarketQuery:
    side = request.get("side")
    if side not in _SIDES:
        raise ValueError(f"side: not one of {sorted(_SIDES)}")
    pad = request.get("pad")
    if pad is not None and pad not in _PADS:
        raise ValueError(f"pad: not one of {sorted(_PADS)}")
    carriers = request.get("carriers")
    if not isinstance(carriers, bool):
        raise ValueError("carriers: not true or false")
    return MarketQuery(
        _SIDES[side],
        text(request, "commodity"),
        text(request, "system"),
        max_distance=number(request, "maxDistance"),
        needed_pad=_PADS[pad] if pad is not None else None,
        carriers=carriers,
        min_volume=whole(request, "minVolume"),
    )


def status[T](answer: Answer[T]) -> dict[str, Any]:
    """Where an answer comes from and how old it is, or why the source gave nothing."""
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
        "readAt": date(answer.read_at),
        "unavailable": answer.unavailable.value if answer.unavailable else None,
    }


def not_asked(reason: str) -> dict[str, Any]:
    """The status of a question the core did not ask: a form it refused (``invalid``), one it
    could not ask (``noSystem``, ``empty``), or the sources' silence (``down``)."""
    return {"status": reason, "source": None, "readAt": None, "unavailable": None}


def offer_view(offer: MarketOffer) -> dict[str, Any]:
    return {
        "station": offer.station,
        "system": offer.system,
        "stationType": offer.station_type,
        "pad": pad_name(offer.pad),
        "arrival": offer.arrival,
        "price": offer.price,
        "volume": offer.volume,
        "distance": offer.distance,
        "updated": date(offer.updated),
        "carrier": offer.is_carrier,
    }


def markets_view(answer: Answer[tuple[MarketOffer, ...]]) -> dict[str, Any]:
    offers = () if isinstance(answer, Failed) else answer.value
    return {**status(answer), "offers": [offer_view(offer) for offer in offers]}


def markets_refused(reason: str) -> dict[str, Any]:
    return {**not_asked(reason), "offers": []}


def estimate_view(
    answer: Answer[CargoEstimate], system: str, name: Callable[[str], str]
) -> dict[str, Any]:
    """``name``: a commodity's name in the player's language, by its key."""
    view = status(answer)
    if not isinstance(answer, Found):
        return {**view, "system": system, "lines": [], "total": 0}
    return {
        **view,
        "system": system,
        "lines": [
            {
                "commodity": line.commodity,
                "name": name(line.commodity),
                "tons": line.tons,
                "value": line.value,
                "offer": offer_view(line.best) if line.best is not None else None,
            }
            for line in answer.value.lines
        ],
        "total": answer.value.total,
    }


def estimate_refused(reason: str) -> dict[str, Any]:
    return {**not_asked(reason), "system": None, "lines": [], "total": 0}
