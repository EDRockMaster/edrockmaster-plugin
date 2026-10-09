"""The demo mode: the sample journal, written as the game would, ending now."""

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from edrockmaster.desktop.core import DesktopCore
from edrockmaster.desktop.demo import DEMO_JOURNAL, ENGLISH, SHOWN_NAMES, write_demo_journal

NOW = datetime(2026, 10, 9, 21, 30, 15, 123456, tzinfo=UTC)


def _lines(journal: Path) -> list[dict[str, Any]]:
    data = journal.read_bytes()
    assert data.endswith(b"\r\n")
    return [json.loads(line) for line in data.split(b"\r\n")[:-1]]


def test_the_demo_journal_ends_now(tmp_path: Path) -> None:
    journal = write_demo_journal(tmp_path / "journal", NOW)
    entries = _lines(journal)
    shipped = [json.loads(line) for line in DEMO_JOURNAL.read_text(encoding="utf-8").splitlines()]
    assert [entry["event"] for entry in entries] == [entry["event"] for entry in shipped]
    assert entries[-1]["timestamp"] == "2026-10-09T21:30:15Z"
    assert journal.name == f"Journal.{entries[0]['timestamp'][:-1].replace(':', '')}.01.log"
    # The gaps between entries are kept
    first, last = (datetime.fromisoformat(entries[i]["timestamp"]) for i in (0, -1))
    shipped_first, shipped_last = (datetime.fromisoformat(shipped[i]["timestamp"]) for i in (0, -1))
    assert last - first == shipped_last - shipped_first


def _shown_names(entries: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in SHOWN_NAMES and isinstance(item, str):
                    names.add(item)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for entry in entries:
        # Materials are named by the catalogue
        if entry["event"] not in {"Materials", "MaterialCollected", "Docked", "Location"}:
            walk(entry)
    return names


def test_the_names_the_application_shows_are_in_english_for_a_demo_in_english(
    tmp_path: Path,
) -> None:
    french = _shown_names(_lines(write_demo_journal(tmp_path / "fr", NOW, "fr")))
    assert french <= set(ENGLISH)
    english = _shown_names(_lines(write_demo_journal(tmp_path / "en", NOW, "en")))
    assert english == {ENGLISH[name] for name in french}
    assert "Methane Clathrate" in english


def test_materials_are_named_by_the_catalogue_in_a_demo_in_english(tmp_path: Path) -> None:
    english = _lines(write_demo_journal(tmp_path / "en", NOW, "en"))
    materials = [e for e in english if e["event"] in {"Materials", "MaterialCollected"}]
    assert materials
    assert "_Localised" not in json.dumps(materials)
    french = _lines(write_demo_journal(tmp_path / "fr", NOW, "fr"))
    assert "Carbone" in json.dumps([e for e in french if e["event"] == "Materials"])


def test_a_short_journal(tmp_path: Path) -> None:
    source = tmp_path / "demo.jsonl"
    source.write_text(
        '{"timestamp": "2026-10-04T02:00:00Z", "event": "Music"}\n'
        '{"timestamp": "2026-10-04T02:10:30Z", "event": "Commander", "Name": "Jameson"}\n',
        encoding="utf-8",
    )
    journal = write_demo_journal(tmp_path / "journal", NOW, "en", source)
    assert journal.name == "Journal.2026-10-09T211945.01.log"
    assert [entry["timestamp"] for entry in _lines(journal)] == [
        "2026-10-09T21:19:45Z",
        "2026-10-09T21:30:15Z",
    ]


def test_the_demo_shows_running_sessions_of_commander_jameson(tmp_path: Path) -> None:
    folder = tmp_path / "journal"
    write_demo_journal(folder, datetime.now(UTC), "en")
    views: list[dict[str, Any]] = []
    core = DesktopCore(
        data_directory=tmp_path / "data",
        journal_folder=folder,
        push=views.append,
        language="en",
        logger=logging.getLogger("test.demo"),
        poll_interval=0.05,
    )
    core.start()
    core.ready()

    def mining(view: dict[str, Any]) -> dict[str, Any]:
        return next(block for block in view["activities"] if block["activity"] == "mining")

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not (views and mining(views[-1])["lines"]):
        time.sleep(0.05)
    time.sleep(0.3)  # the whole journal
    core.stop()
    view = views[-1]
    situation = view["situation"]
    assert situation["commander"] == "Jameson"
    assert situation["ship"] == {"type": "Python", "name": "Rock Hound", "ident": "ED-01"}
    assert situation["gameRunning"] is True
    running = {block["activity"] for block in view["activities"] if block["canReset"]}
    assert running == {"mining", "combat", "engineering"}
    assert view["engineering"]["inventoryKnown"] is True
    assert view["engineering"]["engineers"]
    materials = {row["symbol"]: row["name"] for row in view["engineering"]["materials"]}
    assert materials["carbon"] == "Carbon"
