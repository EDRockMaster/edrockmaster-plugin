"""The Trade tab through the desktop core (ADR 0047): real threads and database, no network."""

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
    assert options["sources"] == {"ardent": True}
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
            journal_line("Location", StarSystem="Sol", SystemAddress=10477373803),
            journal_line("Loadout", Ship="type9", ShipID=1, CargoCapacity=720),
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
