"""The commodities the game trades, by category (ADR 0047).

Imported from EDCD's FDevIDs (``commodity.csv``, ``rare_commodity.csv``) by
``scripts/import_commodities.py`` into ``commodities.json``, beside this module, with
the commit they come from. Each commodity is known by its key, the journal's symbol
in lower case (``Commodity.key``), which the community sources use too; its name is
FDevIDs' English one, translated by the application's catalogues.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum


class CommodityCategory(Enum):
    """The market's categories, in the order the game lists them."""

    CHEMICALS = "Chemicals"
    CONSUMER_ITEMS = "Consumer Items"
    FOODS = "Foods"
    INDUSTRIAL_MATERIALS = "Industrial Materials"
    LEGAL_DRUGS = "Legal Drugs"
    MACHINERY = "Machinery"
    MEDICINES = "Medicines"
    METALS = "Metals"
    MINERALS = "Minerals"
    SALVAGE = "Salvage"
    SLAVERY = "Slavery"
    TECHNOLOGY = "Technology"
    TEXTILES = "Textiles"
    WASTE = "Waste"
    WEAPONS = "Weapons"


@dataclass(frozen=True, slots=True)
class TradedCommodity:
    key: str
    """The journal's symbol in lower case (``Commodity.key``)."""
    name: str
    """FDevIDs' English name."""
    category: CommodityCategory
    rare: bool
    """Sold by one station only, in small quantities."""


@dataclass(frozen=True, slots=True)
class CatalogueSource:
    """Where the catalogue was imported from."""

    repository: str
    commit: str
    date: str


class CommodityCatalogue:
    def __init__(self, commodities: Iterable[TradedCommodity], source: CatalogueSource) -> None:
        self._commodities = {commodity.key: commodity for commodity in commodities}
        self.source = source

    def __len__(self) -> int:
        return len(self._commodities)

    def __contains__(self, key: object) -> bool:
        return key in self._commodities

    def get(self, key: str) -> TradedCommodity | None:
        return self._commodities.get(key)

    @property
    def commodities(self) -> tuple[TradedCommodity, ...]:
        return tuple(self._commodities.values())

    def by_category(self) -> Mapping[CommodityCategory, tuple[TradedCommodity, ...]]:
        """Each category that has commodities, in the game's order; the interface sorts the
        commodities by their name in the player's language."""
        grouped = {
            category: tuple(c for c in self._commodities.values() if c.category is category)
            for category in CommodityCategory
        }
        return {category: rows for category, rows in grouped.items() if rows}
