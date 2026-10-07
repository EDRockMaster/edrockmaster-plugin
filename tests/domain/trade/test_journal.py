from datetime import UTC, datetime

import pytest

from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.trade.journal import (
    CargoEjected,
    CargoInventory,
    CargoTransferred,
    CommanderDied,
    Docked,
    GameClosed,
    GameLoaded,
    GoodsBought,
    GoodsSold,
    Market,
    Transfer,
    TransferDirection,
    Undocked,
    parse_entry,
)

TS = "2026-10-04T14:24:33Z"
AT = datetime(2026, 10, 4, 14, 24, 33, tzinfo=UTC)
PALLADIUM = Commodity("palladium")
CMM = Commodity("cmmcomposite")
AMANO = 4300769795


def test_purchase_is_parsed() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "MarketBuy",
            "MarketID": AMANO,
            "Type": "cmmcomposite",
            "Type_Localised": "Composite MMC",
            "Count": 1040,
            "BuyPrice": 5387,
            "TotalCost": 5602480,
        }
    )
    assert fact == GoodsBought(AT, AMANO, CMM, 1040, 5387, 5602480)
    assert isinstance(fact, GoodsBought)
    assert fact.commodity.display_name == "Composite MMC"


def test_sale_of_bought_goods_has_a_profit() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "MarketSell",
            "MarketID": 4356317443,
            "Type": "palladium",
            "Count": 1040,
            "SellPrice": 53972,
            "TotalSale": 56130880,
            "AvgPricePaid": 4853,
        }
    )
    assert fact == GoodsSold(AT, 4356317443, PALLADIUM, 1040, 53972, 56130880, 4853)
    assert isinstance(fact, GoodsSold)
    assert fact.bought
    assert fact.profit == (53972 - 4853) * 1040


@pytest.mark.parametrize("average", [{"AvgPricePaid": 0}, {}])
def test_sale_of_goods_not_bought(average: dict[str, int]) -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "MarketSell",
            "MarketID": AMANO,
            "Type": "painite",
            "Count": 10,
            "SellPrice": 300_000,
            "TotalSale": 3_000_000,
            **average,
        }
    )
    assert isinstance(fact, GoodsSold)
    assert not fact.bought


def test_docking_names_the_market() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "Docked",
            "StationName": "Amano Terminal",
            "StationType": "Orbis",
            "StarSystem": "Col 359 Sector IL-X d1-126",
            "MarketID": AMANO,
        }
    )
    assert fact == Docked(AT, Market(AMANO, "Amano Terminal", "Col 359 Sector IL-X d1-126"))


def test_markets_are_the_same_whatever_their_names() -> None:
    assert Market(AMANO, "Amano Terminal") == Market(AMANO)


def test_undocking() -> None:
    assert parse_entry({"timestamp": TS, "event": "Undocked", "MarketID": AMANO}) == Undocked(AT)


@pytest.mark.parametrize("event", ["Location", "StartUp"])
def test_game_loaded_docked(event: str) -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": event,
            "Docked": True,
            "StationName": "Verne Venture",
            "MarketID": 4356317443,
            "StarSystem": "Col 285 Sector ZE-A b29-3",
        }
    )
    assert fact == GameLoaded(AT, Market(4356317443))


@pytest.mark.parametrize(
    "entry",
    [
        {"Docked": False, "StarSystem": "Iyakajauja"},
        {"StarSystem": None, "Docked": False},
        {"Docked": True},  # docked, but the game does not say where
    ],
)
def test_game_loaded_in_flight(entry: dict[str, object]) -> None:
    assert parse_entry({"timestamp": TS, "event": "Location", **entry}) == GameLoaded(AT, None)


def test_cargo_ejected() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "EjectCargo",
            "Type": "palladium",
            "Count": 3,
            "Abandoned": True,
        }
    )
    assert fact == CargoEjected(AT, PALLADIUM, 3)


def test_cargo_inventory_of_the_ship() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "Cargo",
            "Vessel": "Ship",
            "Count": 1042,
            "Inventory": [
                {"Name": "palladium", "Count": 1040, "Stolen": 0},
                {"Name": "drones", "Name_Localised": "Limpet", "Count": 2, "Stolen": 0},
            ],
        }
    )
    assert fact == CargoInventory(AT, ((PALLADIUM, 1040), (Commodity("drones"), 2)))


@pytest.mark.parametrize(
    "entry",
    [
        {"Vessel": "SRV", "Count": 0, "Inventory": []},
        {"Vessel": "Ship", "Count": 12},  # the full inventory is in Cargo.json
    ],
)
def test_cargo_without_the_ship_inventory_is_ignored(entry: dict[str, object]) -> None:
    assert parse_entry({"timestamp": TS, "event": "Cargo", **entry}) is None


def test_death_and_game_closed() -> None:
    assert parse_entry({"timestamp": TS, "event": "Died"}) == CommanderDied(AT)
    assert parse_entry({"timestamp": TS, "event": "Shutdown"}) == GameClosed(AT)
    assert parse_entry({"timestamp": TS, "event": "ShutDown"}) == GameClosed(AT)


@pytest.mark.parametrize(
    "entry",
    [
        {"event": "MarketBuy", "MarketID": AMANO, "Type": "gold", "Count": 0},
        {"event": "MarketSell", "MarketID": AMANO, "Type": "gold", "Count": "1"},
        {"event": "Docked", "StationName": "Amano Terminal"},
        {"event": "Market", "MarketID": AMANO},
    ],
)
def test_malformed_or_irrelevant_entries_are_ignored(entry: dict[str, object]) -> None:
    assert parse_entry({"timestamp": TS, **entry}) is None


def test_a_fleet_carrier_is_known_by_its_station_type() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "Docked",
            "StationName": "TZF-66Z",
            "StationType": "FleetCarrier",
            "MarketID": 3711717120,
        }
    )
    assert isinstance(fact, Docked)
    assert fact.market.fleet_carrier
    assert not Market(AMANO, "Amano Terminal").fleet_carrier


def test_game_loaded_at_a_fleet_carrier() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "Location",
            "Docked": True,
            "StationName": "TZF-66Z",
            "StationType": "FleetCarrier",
            "MarketID": 3711717120,
        }
    )
    assert isinstance(fact, GameLoaded)
    assert fact.market is not None
    assert fact.market.fleet_carrier


def test_cargo_transfers_are_parsed() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "CargoTransfer",
            "Transfers": [
                {"Type": "gold", "Type_Localised": "Or", "Count": 1040, "Direction": "tocarrier"},
                {"Type": "tritium", "Count": 10, "Direction": "toship"},
                {"Type": "water", "Count": 1, "Direction": "tosrv"},
            ],
        }
    )
    assert fact == CargoTransferred(
        AT,
        (
            Transfer(Commodity("gold"), 1040, TransferDirection.TO_CARRIER),
            Transfer(Commodity("tritium"), 10, TransferDirection.TO_SHIP),
            Transfer(Commodity("water"), 1, TransferDirection.TO_SRV),
        ),
    )


def test_a_transfer_in_an_unknown_direction_is_ignored() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "CargoTransfer",
            "Transfers": [
                {"Type": "gold", "Count": 1, "Direction": "tospace"},
                {"Type": "gold", "Count": 2, "Direction": "tocarrier"},
            ],
        }
    )
    assert fact == CargoTransferred(
        AT, (Transfer(Commodity("gold"), 2, TransferDirection.TO_CARRIER),)
    )


@pytest.mark.parametrize(
    "transfers",
    [
        "gold",
        [{"Type": "gold", "Count": 0, "Direction": "tocarrier"}],
        [{"Type": "gold", "Count": 1}],
    ],
)
def test_malformed_transfers_are_ignored(transfers: object) -> None:
    assert parse_entry({"timestamp": TS, "event": "CargoTransfer", "Transfers": transfers}) is None
