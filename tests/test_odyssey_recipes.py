"""The rules of data/odyssey/recipes.toml hold for every recipe (ADR 0030).

A deduced recipe follows from rules read in game. When a new reading in game contradicts a
rule, these tests fail: the recipes deduced from it are removed until checked (ADR 0030).
"""

import tomllib
from collections import defaultdict
from typing import Any

import pytest

from tests.scripts import load_script

importer = load_script("import_engineering_data")

RECIPES: dict[str, Any] = tomllib.loads(importer.DEFAULT_RECIPES.read_text(encoding="utf-8"))
ITEMS: dict[str, Any] = RECIPES["items"]
UPGRADES = [
    (symbol, item, upgrade)
    for symbol, item in ITEMS.items()
    for upgrade in item.get("upgrades", [])
]
SUITS = {symbol: item for symbol, item in ITEMS.items() if item["kind"] == "suit"}
WEAPONS = {symbol: item for symbol, item in ITEMS.items() if item["kind"] == "weapon"}


def _upgrades(item: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {upgrade["to"]: upgrade for upgrade in item.get("upgrades", [])}


@pytest.mark.parametrize(("symbol", "item", "upgrade"), UPGRADES)
def test_quantities_depend_on_the_step(
    symbol: str, item: dict[str, Any], upgrade: dict[str, Any]
) -> None:
    few, many = {2: (1, 2), 3: (2, 5), 4: (4, 9)}[upgrade["to"]]
    assert sorted(upgrade["ingredients"].values()) == [few, few, few, many, many]


@pytest.mark.parametrize(
    "symbol", sorted(symbol for symbol in ITEMS if ITEMS[symbol].get("upgrades"))
)
def test_credits_depend_on_the_step(symbol: str) -> None:
    upgrades = _upgrades(ITEMS[symbol])
    base = upgrades[2]["credits"]
    assert upgrades[3]["credits"] == base * 3.75
    assert upgrades[4]["credits"] == base * 7.5


@pytest.mark.parametrize(
    "symbol", sorted(symbol for symbol in SUITS if SUITS[symbol].get("upgrades"))
)
def test_a_suit_takes_its_plating_and_the_same_four_ingredients(symbol: str) -> None:
    sets = {frozenset(upgrade["ingredients"]) for upgrade in SUITS[symbol]["upgrades"]}
    assert len(sets) == 1
    (ingredients,) = sets
    assert {"suitschematic", "healthmonitor", "manufacturinginstructions", "graphene"} < ingredients
    assert len(ingredients) == 5


def test_a_weapon_takes_the_ingredients_of_its_maker() -> None:
    by_maker: dict[str, set[frozenset[str]]] = defaultdict(set)
    for item in WEAPONS.values():
        for upgrade in item["upgrades"]:
            by_maker[item["maker"]].add(frozenset(upgrade["ingredients"]))
    assert {maker: len(sets) for maker, sets in by_maker.items()} == {
        "Kinematic": 1,
        "Takada": 1,
        "Manticore": 1,
    }
    for sets in by_maker.values():
        (ingredients,) = sets
        assert {"weaponschematic", "manufacturinginstructions"} < ingredients
