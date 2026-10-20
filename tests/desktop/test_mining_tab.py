"""The Mining tab through the desktop core (ADR 0040): real threads and database, no network."""

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from edrockmaster.desktop.core import DesktopCore
from tests.desktop.schemas import validate
from tests.fakes import FixedClock
from tests.infrastructure.sources.test_http import FakeResponse

SOURCES = Path(__file__).resolve().parents[1] / "fixtures" / "sources"
SPANSH = json.loads((SOURCES / "spansh-bodies-search-painite-borann-2026-10-11.json").read_text())
ARDENT = json.loads((SOURCES / "ardent-nearby-imports-painite-borann-2026-10-11.json").read_text())
EXPORTS = json.loads((SOURCES / "ardent-nearby-exports-gold-sol-2026-10-20.json").read_text())
NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
logger = logging.getLogger("test.mining_tab")

HOTSPOTS = {
    "commodity": "painite",
    "system": "Borann",
    "minimumCount": 2,
    "reserves": ["pristine", "major"],
    "maxDistance": 20,
    "page": 0,
}
BUYERS = {
    "side": "sell",
    "commodity": "painite",
    "system": "Borann",
    "maxDistance": 50,
    "pad": "large",
    "carriers": False,
    "minVolume": 1,
}


def valid(definition: str, view: dict[str, Any]) -> dict[str, Any]:
    schema = "markets" if definition == "MarketsAnswer" else "mining"
    result: dict[str, Any] = validate(schema, definition, view)
    return result


class Sources:
    """Spansh and Ardent (importers and exporters) as recorded; ``down`` makes them
    unreachable."""

    def __init__(self) -> None:
        self.requests: list[urllib.request.Request] = []
        self.down = False
        self.hold: threading.Event | None = None

    def __call__(self, request: urllib.request.Request, timeout: float) -> FakeResponse:
        self.requests.append(request)
        if self.hold is not None:
            self.hold.wait(5)
        if self.down:
            raise urllib.error.URLError("no network")
        url = request.full_url
        answer = SPANSH if "spansh" in url else EXPORTS if "/nearby/exports" in url else ARDENT
        return FakeResponse(json.dumps(answer).encode())


class Mining:
    def __init__(self, tmp_path: Path, journal: Path | None) -> None:
        self.sources = Sources()
        self.core = DesktopCore(
            data_directory=tmp_path / "data",
            journal_folder=journal,
            push=lambda view: None,
            language="fr",
            logger=logger,
            clock=FixedClock(NOW),
            poll_interval=0.01,
            usual_journal_folder=lambda: None,
            logs_directory=tmp_path / "logs",
            http_opener=self.sources,
        )


@pytest.fixture
def mining(tmp_path: Path) -> Iterator[Mining]:
    started = Mining(tmp_path, None)
    started.core.start()
    yield started
    started.core.stop()


def test_the_forms_start_from_the_commodities_with_hotspots(mining: Mining) -> None:
    options = valid("MiningOptions", mining.core.handlers.mining.mining_options())
    assert len(options["commodities"]) == 13
    names = {row["commodity"]: row["name"] for row in options["commodities"]}
    assert names["platinum"] == "Platine"  # in the player's language
    assert (options["system"], options["pad"]) == (None, None)  # no journal read yet
    assert options["sources"] == {"spansh": True, "ardent": True}
    assert mining.sources.requests == []  # nothing asked to show the form


def test_where_to_mine(mining: Mining) -> None:
    answer = valid("HotspotsAnswer", mining.core.handlers.mining.find_hotspots(HOTSPOTS))
    assert (answer["status"], answer["source"], answer["total"]) == ("found", "spansh", 5)
    borann = answer["rings"][0]
    assert (borann["ring"], borann["count"], borann["reserve"]) == (
        "Borann A 2 A Ring",
        10,
        "pristine",
    )
    assert {other["name"] for other in borann["others"]} >= {"Platine", "Sérendibite"}
    [request] = mining.sources.requests
    assert str(request.get_header("User-agent")).startswith("EDRockMaster/")
    # The same search again comes from the cache
    mining.core.handlers.mining.find_hotspots(HOTSPOTS)
    assert len(mining.sources.requests) == 1
    mining.core.handlers.mining.find_hotspots({**HOTSPOTS, "refresh": True})
    assert len(mining.sources.requests) == 2


def test_where_to_sell(mining: Mining) -> None:
    answer = valid("MarketsAnswer", mining.core.handlers.trade.find_markets(BUYERS))
    assert answer["status"] == "found"
    assert [offer["station"] for offer in answer["offers"]] == [
        "Borisenko's Folly",
        "Sarich Prospect",
        "Rey Sanctuary",
        "Laumer Terminal",
    ]  # large pads only, no carrier, best price first
    assert "fleetCarriers=false" in mining.sources.requests[0].full_url


@pytest.mark.parametrize(
    ("call", "request_"),
    [
        ("find_hotspots", {**HOTSPOTS, "commodity": "gold"}),
        ("find_hotspots", {**HOTSPOTS, "reserves": ["bottomless"]}),
        ("find_hotspots", {**HOTSPOTS, "page": -1}),
        ("find_markets", {**BUYERS, "pad": "huge"}),
        ("find_markets", {**BUYERS, "carriers": "no"}),
        ("find_markets", {**BUYERS, "maxDistance": 900}),
        ("find_markets", {**BUYERS, "side": "steal"}),
        ("find_markets", {**BUYERS, "minVolume": 0}),
        ("find_markets", {**BUYERS, "minVolume": 1.5}),
    ],
)
def test_a_form_the_core_refuses_asks_nothing(
    mining: Mining, call: str, request_: dict[str, Any]
) -> None:
    handlers = mining.core.handlers
    answer = getattr(handlers.trade if call == "find_markets" else handlers.mining, call)(request_)
    assert answer["status"] == "invalid"
    assert mining.sources.requests == []


def test_a_source_down_and_a_source_turned_off(mining: Mining) -> None:
    mining.sources.down = True
    assert mining.core.handlers.trade.find_markets(BUYERS)["status"] == "down"
    mining.sources.down = False
    mining.core.handlers.mining.find_hotspots(HOTSPOTS)
    settings = mining.core.handlers.settings.settings()
    handlers = mining.core.handlers
    handlers.settings.save_settings({**settings, "sources": {"spansh": False, "ardent": True}})
    answer = valid("HotspotsAnswer", mining.core.handlers.mining.find_hotspots(HOTSPOTS))
    assert (answer["status"], answer["rings"]) == ("off", [])
    database = mining.core.database
    assert database is not None
    asked = len(mining.sources.requests)
    handlers.settings.save_settings({**settings, "sources": {"spansh": True, "ardent": True}})
    mining.core.handlers.mining.find_hotspots(HOTSPOTS)  # its cache was cleared: asked again
    assert len(mining.sources.requests) == asked + 1


def test_no_estimate_before_the_system_or_a_cargo_is_known(mining: Mining) -> None:
    answer = mining.core.handlers.mining.estimate_cargo()
    assert valid("CargoEstimateAnswer", answer)["status"] == "noSystem"


def journal_line(event: str, **fields: Any) -> str:
    return json.dumps({"timestamp": "2026-10-12T08:00:00Z", "event": event, **fields}) + "\r\n"


def test_the_cargo_at_the_best_markets(tmp_path: Path) -> None:
    folder = tmp_path / "journal"
    folder.mkdir()
    started = Mining(tmp_path, folder)
    started.core.start()
    try:
        lines = [
            journal_line("Location", StarSystem="Borann", SystemAddress=5070611621289),
            journal_line("Loadout", Ship="anaconda", ShipID=1),
            *[journal_line("MiningRefined", Type="$painite_name;") for _ in range(3)],
            journal_line("MiningRefined", Type="$platinum_name;"),
        ]
        (folder / "Journal.2026-10-12T080000.01.log").write_text("".join(lines), newline="")
        answer: dict[str, Any] = {}
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            answer = started.core.handlers.mining.estimate_cargo()
            if answer["status"] == "found":
                break
            time.sleep(0.05)
    finally:
        started.core.stop()
    valid("CargoEstimateAnswer", answer)
    assert answer["system"] == "Borann"
    assert [(line["commodity"], line["tons"]) for line in answer["lines"]] == [
        ("painite", 3),
        ("platinum", 1),
    ]
    assert answer["lines"][0]["offer"]["station"] == "Borisenko's Folly"
    assert answer["total"] == 4 * 91254


def test_no_estimate_without_cargo(tmp_path: Path) -> None:
    folder = tmp_path / "journal"
    folder.mkdir()
    started = Mining(tmp_path, folder)
    started.core.start()
    try:
        line = journal_line("Location", StarSystem="Borann", SystemAddress=5070611621289)
        (folder / "Journal.2026-10-12T080000.01.log").write_text(line, newline="")
        answer: dict[str, Any] = {}
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            answer = started.core.handlers.mining.estimate_cargo()
            if answer["status"] != "noSystem":
                break
            time.sleep(0.05)
    finally:
        started.core.stop()
    assert valid("CargoEstimateAnswer", answer)["status"] == "empty"
    assert started.sources.requests == []
