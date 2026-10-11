"""The ship type names imported from FDevIDs (ADR 0023)."""

import json
from pathlib import Path
from typing import Any

import pytest

from edrockmaster.infrastructure.ship_names_file import SHIP_NAMES_FILE, load_ship_names
from tests.scripts import load_script

importer = load_script("import_ship_names")

SHIPYARD = """id,symbol,name,entitlement
128049249,SideWinder,Sidewinder,
129034269,PantherMkII,Panther Clipper MkII,ELITE_V_PANTHER_MKII
"""


def read(source: Any, path: str) -> str:
    assert path == "shipyard.csv"
    return SHIPYARD


def test_names_by_lower_case_symbol(tmp_path: Path) -> None:
    output = tmp_path / "ship_names.json"
    assert importer.main(["import", str(output)], read) == 0
    assert load_ship_names(output) == {
        "panthermkii": "Panther Clipper MkII",
        "sidewinder": "Sidewinder",
    }


def test_a_ship_without_its_name_is_refused(tmp_path: Path) -> None:
    output = tmp_path / "ship_names.json"
    assert importer.main(["import", str(output)], lambda _s, _p: SHIPYARD + "1,Ghost,,\n") == 1
    assert not output.exists()


def test_usage() -> None:
    assert importer.main(["import", "a", "b"]) == 2


def test_the_shipped_names_have_every_ship_of_the_player() -> None:
    names = load_ship_names()
    assert names["panthermkii"] == "Panther Clipper MkII"
    assert names["type9"] == "Type-9 Heavy"
    assert json.loads(SHIP_NAMES_FILE.read_text(encoding="utf-8")) == names


def test_a_file_that_is_no_table_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "ship_names.json"
    bad.write_text('{"a": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="ship names"):
        load_ship_names(bad)
