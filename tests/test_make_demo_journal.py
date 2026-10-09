import json
from pathlib import Path

import pytest

from tests.scripts import load_script

maker = load_script("make_demo_journal")


def test_the_shipped_demo_journal_is_up_to_date(tmp_path: Path) -> None:
    written = maker.write(tmp_path / "demo.jsonl")
    assert written.read_bytes() == maker.DEMO_JOURNAL.read_bytes(), (
        "run python3 scripts/make_demo_journal.py"
    )


def test_only_the_fictional_commander_is_named() -> None:
    entries = maker.demo_entries()
    named = {entry.get("Name") for entry in entries if entry["event"] == "Commander"}
    named |= {entry.get("Commander") for entry in entries if entry["event"] == "LoadGame"}
    assert named == {"Jameson"}
    assert {entry.get("FID") for entry in entries} <= {None, "F0"}
    assert not any(entry["event"] in {"StartUp", "WingJoin", "WingAdd"} for entry in entries)


def test_the_commander_is_still_mining_at_the_end() -> None:
    events = [entry["event"] for entry in maker.demo_entries()]
    last_refined = len(events) - 1 - events[::-1].index("MiningRefined")
    assert "SupercruiseEntry" not in events[last_refined:]
    assert "Shutdown" not in events
    assert events.count("MaterialCollected") > 0
    assert events[:2] == ["Commander", "LoadGame"]


def test_usage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert maker.main(["a", "b"]) == 2
    assert maker.main([str(tmp_path / "demo.jsonl")]) == 0
    assert json.loads((tmp_path / "demo.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert "demo.jsonl" in capsys.readouterr().out
