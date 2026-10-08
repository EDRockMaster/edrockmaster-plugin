import json
from pathlib import Path

import pytest

from tests.scripts import load_script

converter = load_script("fixture_to_journal")
FIXTURE = Path(__file__).parent / "fixtures" / "engineering-power-distributor-2026-10-08.jsonl"


def test_a_fixture_becomes_a_journal_file(tmp_path: Path) -> None:
    journal = converter.write(FIXTURE, tmp_path / "journal")
    assert journal.name == "Journal.2026-10-08T014139.01.log"
    lines = journal.read_bytes().split(b"\r\n")
    records = FIXTURE.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(records) + 1  # the last line ends too
    assert json.loads(lines[0]) == json.loads(records[0])["entry"]


def test_usage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert converter.main([]) == 2
    assert converter.main([str(FIXTURE), str(tmp_path)]) == 0
    assert "Journal." in capsys.readouterr().out
