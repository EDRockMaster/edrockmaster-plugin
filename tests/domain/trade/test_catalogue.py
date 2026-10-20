"""The commodities the game trades, by category (ADR 0047)."""

from edrockmaster.domain.trade.catalogue import (
    CatalogueSource,
    CommodityCatalogue,
    CommodityCategory,
    TradedCommodity,
)

GOLD = TradedCommodity("gold", "Gold", CommodityCategory.METALS, rare=False)
WATER = TradedCommodity("water", "Water", CommodityCategory.CHEMICALS, rare=False)
SILVER = TradedCommodity("silver", "Silver", CommodityCategory.METALS, rare=False)
SOURCE = CatalogueSource("EDCD/FDevIDs", "c" * 40, "2026-09-05")


def test_found_by_key() -> None:
    catalogue = CommodityCatalogue([GOLD, WATER], SOURCE)
    assert (len(catalogue), "gold" in catalogue, catalogue.get("gold")) == (2, True, GOLD)
    assert catalogue.get("unobtainium") is None


def test_by_category_in_the_game_s_order_without_empty_ones() -> None:
    catalogue = CommodityCatalogue([GOLD, WATER, SILVER], SOURCE)
    assert catalogue.by_category() == {
        CommodityCategory.CHEMICALS: (WATER,),
        CommodityCategory.METALS: (GOLD, SILVER),
    }
