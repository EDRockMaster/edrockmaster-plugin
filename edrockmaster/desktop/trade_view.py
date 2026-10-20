"""The *Trade* tab (ADR 0047): what its forms start from, the galaxy's prices of a commodity,
the station's market and the trade routes (ADR 0057), as ``schemas/trade.schema.json``
describes them. Where to buy and
where to sell are the market search's, shared with the Mining tab (``market_view.py``).

Names are in the player's language, the commodities of a category sorted by them.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Mapping
from datetime import timedelta
from typing import Any

from edrockmaster.application.community import Answer, Failed, Found, Pending
from edrockmaster.application.route_planner import RouteProgress
from edrockmaster.application.settings import SourceSettings
from edrockmaster.desktop.market_view import (
    PADS,
    date,
    not_asked,
    number,
    pad_name,
    status,
    text,
    whole,
)
from edrockmaster.domain.commodities import GalaxyPrices, PriceRange
from edrockmaster.domain.ships import PadSize
from edrockmaster.domain.trade.catalogue import (
    CommodityCatalogue,
    CommodityCategory,
    TradedCommodity,
)
from edrockmaster.domain.trade.journal import MarketLine
from edrockmaster.domain.trade.routes import RouteHop, RouteQuery, RouteStation
from edrockmaster.domain.trade.station_market import StationMarket

type Translate = Callable[[str], str]


def _sort_key(name: str) -> str:
    """Accents aside, as a reader looks a name up: *Éther* among the E."""
    return "".join(
        letter
        for letter in unicodedata.normalize("NFKD", name.casefold())
        if not unicodedata.combining(letter)
    )


def _name(commodity: TradedCommodity, translate: Translate) -> str:
    # As the game names it on a market, not as a material
    return translate(f"{commodity.name}|commodity")


def commodity_name(catalogue: CommodityCatalogue, key: str, translate: Translate) -> str:
    """A commodity's name in the player's language; its key if the catalogue does not know it."""
    commodity = catalogue.get(key)
    return _name(commodity, translate) if commodity is not None else key


def _commodity_view(commodity: TradedCommodity, translate: Translate) -> dict[str, Any]:
    return {
        "commodity": commodity.key,
        "name": _name(commodity, translate),
        "rare": commodity.rare,
    }


def options_view(  # noqa: PLR0913 - what the forms start from
    catalogue: CommodityCatalogue,
    *,
    system: str | None,
    station: str | None,
    pad: PadSize | None,
    cargo_capacity: int | None,
    jump_range: float | None,
    credits: int | None,
    sources: SourceSettings,
    translate: Translate,
) -> dict[str, Any]:
    """The commodities by category; the current system and station, the ship's pad, cargo
    capacity and jump range, and the commander's credits at load."""
    return {
        "categories": [
            {
                "category": category.name.lower(),
                "name": translate(category.value),
                "commodities": sorted(
                    (_commodity_view(commodity, translate) for commodity in commodities),
                    key=lambda row: _sort_key(str(row["name"])),
                ),
            }
            for category, commodities in catalogue.by_category().items()
        ],
        "system": system,
        "station": station,
        "pad": pad_name(pad),
        "cargoCapacity": cargo_capacity,
        "jumpRange": jump_range,
        "credits": credits,
        "sources": {"ardent": sources.ardent, "spansh": sources.spansh},
    }


def _range_view(prices: PriceRange | None) -> dict[str, int] | None:
    if prices is None:
        return None
    return {"lowest": prices.lowest, "average": prices.average, "highest": prices.highest}


def prices_view(answer: Answer[GalaxyPrices | None]) -> dict[str, Any]:
    prices = None if isinstance(answer, Failed) else answer.value
    return {
        **status(answer),
        "buy": _range_view(prices.buy if prices else None),
        "sell": _range_view(prices.sell if prices else None),
        "computedAt": date(prices.computed_at if prices else None),
    }


def prices_refused(reason: str) -> dict[str, Any]:
    return {**not_asked(reason), "buy": None, "sell": None, "computedAt": None}


type GalaxyAnswer = Answer[Mapping[str, GalaxyPrices]]


def _gap(prices: PriceRange | None, price: int) -> float | None:
    return prices.gap(price) if prices is not None else None


def _line_view(
    line: MarketLine, commodity: TradedCommodity, prices: GalaxyPrices | None, translate: Translate
) -> dict[str, Any]:
    """What the station sells (a stock) and buys (a demand), each with its gap with the galaxy's
    average once compared."""
    return {
        **_commodity_view(commodity, translate),
        "buy": {
            "price": line.buy_price,
            "stock": line.stock,
            "gap": _gap(prices.buy if prices else None, line.buy_price),
        }
        if line.stock > 0
        else None,
        "sell": {
            "price": line.sell_price,
            "demand": line.demand,
            "gap": _gap(prices.sell if prices else None, line.sell_price),
        }
        if line.demand > 0
        else None,
    }


def station_market_view(
    market: StationMarket | None,
    catalogue: CommodityCatalogue,
    comparison: GalaxyAnswer | None,
    translate: Translate,
) -> dict[str, Any]:
    """The station's market by category, as the catalogue sorts them; a commodity the catalogue
    does not know yet (a game update before ``import_commodities.py`` ran) is left out.
    ``comparison``: the galaxy's prices, when the player asked for them."""
    galaxy = comparison.value if isinstance(comparison, Found) else {}
    return {
        "market": None if market is None else _market_view(market, catalogue, galaxy, translate),
        "comparison": None if comparison is None else status(comparison),
    }


def _market_view(
    market: StationMarket,
    catalogue: CommodityCatalogue,
    galaxy: Mapping[str, GalaxyPrices],
    translate: Translate,
) -> dict[str, Any]:
    known = [
        (line, commodity)
        for line in market.lines
        if (commodity := catalogue.get(line.commodity.key)) is not None
    ]
    return {
        "station": market.market.station,
        "system": market.market.system,
        "carrier": market.market.fleet_carrier,
        "readAt": date(market.read_at),
        "categories": [
            {
                "category": category.name.lower(),
                "name": translate(category.value),
                "commodities": sorted(
                    (
                        _line_view(line, commodity, galaxy.get(commodity.key), translate)
                        for line, commodity in known
                        if commodity.category is category
                    ),
                    key=lambda row: _sort_key(str(row["name"])),
                ),
            }
            for category in CommodityCategory
            if any(commodity.category is category for _line, commodity in known)
        ],
    }


def route_query(request: Mapping[str, Any]) -> RouteQuery:
    """The route form as a query; ``ValueError`` for what is not valid."""
    pad = request.get("pad")
    if pad is not None and pad not in PADS:
        raise ValueError(f"pad: not one of {sorted(PADS)}")
    flags = {name: request.get(name) for name in ("planetary", "carriers")}
    for name, value in flags.items():
        if not isinstance(value, bool):
            raise ValueError(f"{name}: not true or false")
    return RouteQuery(
        text(request, "system"),
        text(request, "station"),
        cargo_capacity=whole(request, "cargoCapacity"),
        credits=whole(request, "credits"),
        max_hops=whole(request, "maxHops"),
        max_hop_distance=number(request, "maxHopDistance"),
        needed_pad=PADS[pad] if pad is not None else None,
        max_price_age=timedelta(days=whole(request, "maxPriceDays")),
        planetary=flags["planetary"] is True,
        carriers=flags["carriers"] is True,
    )


def _station_view(station: RouteStation) -> dict[str, Any]:
    return {
        "station": station.station,
        "system": station.system,
        "arrival": station.arrival,
        "pricesUpdated": date(station.prices_updated),
    }


def _hop_view(hop: RouteHop, translate: Translate) -> dict[str, Any]:
    return {
        "source": _station_view(hop.source),
        "destination": _station_view(hop.destination),
        "distance": hop.distance,
        "profit": hop.profit,
        "commodities": [
            {
                # Spansh names commodities in English, as the catalogue does
                "name": translate(f"{goods.name}|commodity"),
                "tons": goods.tons,
                "buyPrice": goods.buy_price,
                "sellPrice": goods.sell_price,
                "profit": goods.profit,
                "totalProfit": goods.total_profit,
            }
            for goods in hop.commodities
        ],
    }


def route_view(progress: RouteProgress, translate: Translate) -> dict[str, Any]:
    """The route found, the job Spansh is still computing, or why Spansh gave nothing."""
    if isinstance(progress, Pending):
        return {
            **not_asked("pending"),
            "source": progress.source.value,
            "job": progress.job,
            "hops": [],
            "profit": 0,
        }
    if isinstance(progress, Failed):
        return {**status(progress), "job": None, "hops": [], "profit": 0}
    route = progress.value
    return {
        **status(progress),
        "job": None,
        "hops": [_hop_view(hop, translate) for hop in route.hops],
        "profit": route.profit,
    }


def route_refused(reason: str) -> dict[str, Any]:
    return {**not_asked(reason), "job": None, "hops": [], "profit": 0}
