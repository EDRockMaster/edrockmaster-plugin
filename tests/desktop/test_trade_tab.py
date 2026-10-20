"""The Trade tab through the desktop core (ADR 0047): real threads and database, no network."""

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.desktop.schemas import validate
from tests.desktop.test_mining_tab import Mining, journal_line

SELLERS = {
    "side": "buy",
    "commodity": "gold",
    "system": "Sol",
    "maxDistance": 20,
    "pad": None,
    "carriers": False,
    "minVolume": 100,
}


@pytest.fixture
def trade(tmp_path: Path) -> Iterator[Mining]:
    started = Mining(tmp_path, None)
    started.core.start()
    yield started
    started.core.stop()


def test_the_commodities_by_category_in_the_player_s_language(trade: Mining) -> None:
    options = validate("trade", "TradeOptions", trade.core.handlers.trade.trade_options())
    categories = {row["category"]: row for row in options["categories"]}
    assert options["categories"][0]["name"] == "Produits chimiques"  # the game's order
    metals = categories["metals"]
    assert metals["name"] == "Métaux"
    names = [row["name"] for row in metals["commodities"]]
    # By name in French, accents aside
    assert names[:5] == ["Acier", "Alliage de platine", "Aluminium", "Argent", "Béryllium"]
    salvage = categories["salvage"]
    assert salvage["name"] == "Ferraille"  # as the game names it
    wreckage = next(r for r in salvage["commodities"] if r["commodity"] == "wreckagecomponents")
    assert wreckage["name"] == "Débris d'épave"  # not the material's name
    assert {"commodity": "gold", "name": "Or", "rare": False} in metals["commodities"]
    rare = next(row for row in categories["legal_drugs"]["commodities"] if row["rare"])
    assert rare["name"]
    assert (options["system"], options["pad"], options["cargoCapacity"]) == (None, None, None)
    assert (options["station"], options["jumpRange"], options["credits"]) == (None, None, None)
    assert options["sources"] == {"ardent": True, "spansh": True}
    assert trade.sources.requests == []  # nothing asked to show the tab


def test_where_to_buy(trade: Mining) -> None:
    answer = validate("markets", "MarketsAnswer", trade.core.handlers.trade.find_markets(SELLERS))
    assert answer["status"] == "found"
    # No carrier, a stock of 100 t at least, the lowest price first
    assert [(offer["station"], offer["price"], offer["volume"]) for offer in answer["offers"]] == [
        ("Kramer Drilling Territory", 39893, 216),
        ("Berdo Drilling Hub", 40253, 130),
    ]
    [request] = trade.sources.requests
    assert "/nearby/exports?" in request.full_url
    assert "minVolume=100" in request.full_url


def test_the_ship_s_pad_and_cargo_capacity_from_the_journal(tmp_path: Path) -> None:
    folder = tmp_path / "journal"
    folder.mkdir()
    started = Mining(tmp_path, folder)
    started.core.start()
    try:
        lines = [
            journal_line("LoadGame", Commander="Nyx", Ship="type9", Credits=123_456),
            journal_line(
                "Location",
                StarSystem="Sol",
                SystemAddress=10477373803,
                Docked=True,
                StationName="Abraham Lincoln",
            ),
            journal_line("Loadout", Ship="type9", ShipID=1, CargoCapacity=720, MaxJumpRange=18.5),
        ]
        (folder / "Journal.2026-10-12T080000.01.log").write_text("".join(lines), newline="")
        options: dict[str, Any] = {}
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            options = started.core.handlers.trade.trade_options()
            if options["cargoCapacity"] is not None:
                break
            time.sleep(0.05)
    finally:
        started.core.stop()
    assert (options["system"], options["pad"], options["cargoCapacity"]) == ("Sol", "large", 720)
    assert (options["station"], options["jumpRange"], options["credits"]) == (
        "Abraham Lincoln",
        18.5,
        123_456,
    )


def test_the_galaxy_s_prices_of_a_commodity(trade: Mining) -> None:
    handler = trade.core.handlers.trade
    answer = validate("trade", "PricesAnswer", handler.galaxy_prices({"commodity": "gold"}))
    assert (answer["status"], answer["source"]) == ("found", "ardent")
    assert answer["buy"] == {"lowest": 3800, "average": 44779, "highest": 59270}
    assert answer["sell"] == {"lowest": 3799, "average": 47791, "highest": 282678}
    assert answer["computedAt"] == "2026-09-07T03:00:43.257000+00:00"
    # Another commodity: the answer kept a day, nothing asked again
    painite = validate("trade", "PricesAnswer", handler.galaxy_prices({"commodity": "painite"}))
    assert (painite["buy"], painite["sell"]["average"]) == (None, 56364)
    assert len(trade.sources.requests) == 1
    handler.galaxy_prices({"commodity": "painite", "refresh": True})
    assert len(trade.sources.requests) == 2


def test_prices_the_source_does_not_know(trade: Mining) -> None:
    handler = trade.core.handlers.trade
    answer = validate("trade", "PricesAnswer", handler.galaxy_prices({"commodity": "tea"}))
    assert (answer["status"], answer["buy"], answer["sell"], answer["computedAt"]) == (
        "found",
        None,
        None,
        None,
    )
    refused = validate("trade", "PricesAnswer", handler.galaxy_prices({"commodity": " "}))
    assert refused["status"] == "invalid"


def test_prices_with_the_source_down(trade: Mining) -> None:
    trade.sources.down = True
    answer = trade.core.handlers.trade.galaxy_prices({"commodity": "gold"})
    assert (validate("trade", "PricesAnswer", answer)["status"], answer["buy"]) == ("down", None)


def test_the_station_s_market_compared_with_the_galaxy(tmp_path: Path) -> None:
    folder = tmp_path / "journal"
    folder.mkdir()
    started = Mining(tmp_path, folder)
    started.core.start()
    handler = started.core.handlers.trade
    try:
        assert (
            validate("trade", "StationMarketAnswer", handler.station_market({"compare": True}))[
                "market"
            ]
            is None
        )
        assert started.sources.requests == []  # no market: nothing to compare
        stamp = {"MarketID": 1, "StationName": "Yamazaki Landing", "StarSystem": "Sol"}
        gold = {"Name": "$gold_name;", "BuyPrice": 46000, "SellPrice": 45500, "Stock": 9}
        (folder / "Market.json").write_text(
            json.dumps(
                {
                    "timestamp": "2026-10-12T08:00:00Z",
                    "event": "Market",
                    **stamp,
                    "Items": [{**gold, "Demand": 0}],
                }
            )
        )
        (folder / "Journal.2026-10-12T080000.01.log").write_text(
            journal_line("Market", **stamp), newline=""
        )
        answer: dict[str, Any] = {}
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            answer = handler.station_market({"compare": False})
            if answer["market"] is not None:
                break
            time.sleep(0.05)
        assert validate("trade", "StationMarketAnswer", answer)["comparison"] is None
        compared = validate(
            "trade", "StationMarketAnswer", handler.station_market({"compare": True})
        )
    finally:
        started.core.stop()
    assert compared["comparison"]["status"] == "found"
    [metals] = compared["market"]["categories"]
    assert metals["commodities"][0]["name"] == "Or"
    # 46,000 CR asked, against an average of 44,779 CR
    assert round(metals["commodities"][0]["buy"]["gap"], 3) == 0.027
    [request] = started.sources.requests
    assert request.full_url.endswith("/commodities")


def test_the_ship_s_cargo_at_the_best_markets(tmp_path: Path) -> None:
    folder = tmp_path / "journal"
    folder.mkdir()
    started = Mining(tmp_path, folder)
    started.core.start()
    try:
        inventory = [
            {"Name": "painite", "Count": 10, "Stolen": 0},
            {"Name": "drones", "Name_Localised": "Limpet", "Count": 4, "Stolen": 0},
            {"Name": "tea", "Count": 8, "Stolen": 0, "MissionID": 65380901},
        ]
        lines = [
            journal_line("Location", StarSystem="Borann", SystemAddress=5070611621289),
            journal_line("Cargo", Vessel="Ship", Count=22, Inventory=inventory),
        ]
        (folder / "Journal.2026-10-12T080000.01.log").write_text("".join(lines), newline="")
        answer: dict[str, Any] = {}
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            answer = started.core.handlers.trade.estimate_cargo({"hold": "ship"})
            if answer["status"] == "found":
                break
            time.sleep(0.05)
    finally:
        started.core.stop()
    validate("markets", "CargoEstimateAnswer", answer)
    # Neither the limpets nor the tea of a mission
    assert [(line["name"], line["tons"]) for line in answer["lines"]] == [("Painite", 10)]
    assert answer["total"] == 10 * 91254
    assert (
        validate(
            "markets",
            "CargoEstimateAnswer",
            started.core.handlers.trade.estimate_cargo({"hold": "x"}),
        )["status"]
        == "invalid"
    )


ROUTE = {
    "system": "Sol",
    "station": "Abraham Lincoln",
    "cargoCapacity": 720,
    "credits": 100_000_000,
    "maxHops": 3,
    "maxHopDistance": 30,
    "pad": "large",
    "maxPriceDays": 2,
    "planetary": False,
    "carriers": False,
}


def test_a_trade_route_planned_then_followed(trade: Mining) -> None:
    handler = trade.core.handlers.trade
    pending = validate("trade", "RouteAnswer", handler.plan_route(ROUTE))
    assert (pending["status"], pending["source"]) == ("pending", "spansh")
    job = pending["job"]
    computing = validate("trade", "RouteAnswer", handler.follow_route({**ROUTE, "job": job}))
    assert computing["status"] == "pending"  # Spansh still computing
    route = validate("trade", "RouteAnswer", handler.follow_route({**ROUTE, "job": job}))
    assert (route["status"], len(route["hops"]), route["profit"]) == ("found", 3, 26_214_480)
    first = route["hops"][0]
    assert first["commodities"][0]["name"] == "Carburant à base d'hydrogène"
    assert first["source"]["pricesUpdated"] == "2026-10-20T18:11:24+00:00"
    sent = [request.full_url for request in trade.sources.requests]
    assert sent[0] == "https://spansh.co.uk/api/trade/route"
    assert sent[1:] == [f"https://spansh.co.uk/api/results/{job}"] * 2
    # Asked again within 15 minutes: the route kept, nothing sent
    assert handler.plan_route(ROUTE)["status"] == "found"
    assert len(trade.sources.requests) == 3


def test_a_route_form_not_valid_is_refused(trade: Mining) -> None:
    for change in ({"maxHops": 11}, {"pad": "huge"}, {"planetary": "no"}, {"credits": -1}):
        answer = trade.core.handlers.trade.plan_route({**ROUTE, **change})
        assert validate("trade", "RouteAnswer", answer)["status"] == "invalid"
    answer = trade.core.handlers.trade.follow_route(ROUTE)  # no job
    assert answer["status"] == "invalid"
    assert trade.sources.requests == []
