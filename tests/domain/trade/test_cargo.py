"""What the player may sell of the ship's cargo (ADR 0047)."""

from datetime import UTC, datetime

from edrockmaster.domain.commodities import LIMPET, Commodity
from edrockmaster.domain.trade.cargo import cargo_to_sell
from edrockmaster.domain.trade.journal import CargoInventory

AT = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
GOLD, TEA = Commodity("gold"), Commodity("tea")


def test_the_cargo_but_limpets_and_the_goods_of_missions() -> None:
    inventory = CargoInventory(
        AT, ((GOLD, 22), (TEA, 8), (LIMPET, 40)), for_missions=((GOLD, 12), (TEA, 8))
    )
    assert cargo_to_sell(inventory) == {"gold": 10}


def test_no_cargo_known_yet() -> None:
    assert cargo_to_sell(None) == {}
