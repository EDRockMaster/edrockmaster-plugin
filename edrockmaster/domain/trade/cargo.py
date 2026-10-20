"""What the player may sell of the ship's cargo (ADR 0047): mined, bought or salvaged alike,
but neither the limpets nor the goods of missions, which are delivered."""

from __future__ import annotations

from edrockmaster.domain.commodities import LIMPET
from edrockmaster.domain.trade.journal import CargoInventory


def cargo_to_sell(inventory: CargoInventory | None) -> dict[str, int]:
    """Tons by commodity key; empty until the game has told the cargo."""
    if inventory is None:
        return {}
    for_missions = dict(inventory.for_missions)
    tons = {
        goods.key: count - for_missions.get(goods, 0)
        for goods, count in inventory.tons
        if goods != LIMPET
    }
    return {key: count for key, count in tons.items() if count > 0}
