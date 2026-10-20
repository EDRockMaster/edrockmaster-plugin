"""The *Trade* tab (ADR 0047): what its forms start from, the galaxy's prices of a commodity,
and the station's market, as ``schemas/trade.schema.json`` describes them. Where to buy and
where to sell are the market search's, shared with the Mining tab (``market_view.py``).

Names are in the player's language, the commodities of a category sorted by them.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Mapping
from typing import Any

from edrockmaster.application.community import Answer, Failed, Found
from edrockmaster.application.settings import SourceSettings
from edrockmaster.desktop.market_view import date, not_asked, pad_name, status
from edrockmaster.domain.commodities import GalaxyPrices, PriceRange
from edrockmaster.domain.ships import PadSize
from edrockmaster.domain.trade.catalogue import (
    CommodityCatalogue,
    CommodityCategory,
    TradedCommodity,
)
from edrockmaster.domain.trade.journal import MarketLine
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
    pad: PadSize | None,
    cargo_capacity: int | None,
    sources: SourceSettings,
    translate: Translate,
) -> dict[str, Any]:
    """The commodities by category, the current system, the ship's pad and cargo capacity."""
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
        "pad": pad_name(pad),
        "cargoCapacity": cargo_capacity,
        "sources": {"ardent": sources.ardent},
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
