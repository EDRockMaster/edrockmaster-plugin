"""The commodities imported from FDevIDs (ADR 0047)."""

from pathlib import Path
from typing import Any

import pytest

from edrockmaster.domain.trade.catalogue import CommodityCategory
from edrockmaster.infrastructure.commodity_catalogue_file import load_commodities
from tests.scripts import load_script

importer = load_script("import_commodities")

COMMON = """id,symbol,category,name
128049154,Gold,Metals,Gold
128066403,Drones,NonMarketable,Limpets
128049202,HydrogenFuel,Chemicals,Hydrogen Fuel
"""
RARE = """id,symbol,market_id,category,name
128666747,LavianBrandy,128106744,Legal Drugs,Lavian Brandy
"""


def read(files: dict[str, str]) -> Any:
    def reader(_source: Any, path: str) -> str:
        return files[path]

    return reader


def test_the_traded_commodities_by_key(tmp_path: Path) -> None:
    output = tmp_path / "commodities.json"
    files = {"commodity.csv": COMMON, "rare_commodity.csv": RARE}
    assert importer.main(["import", str(output)], read(files)) == 0
    catalogue = load_commodities(output)
    assert [(c.key, c.name, c.category, c.rare) for c in catalogue.commodities] == [
        ("gold", "Gold", CommodityCategory.METALS, False),
        ("hydrogenfuel", "Hydrogen Fuel", CommodityCategory.CHEMICALS, False),
        ("lavianbrandy", "Lavian Brandy", CommodityCategory.LEGAL_DRUGS, True),
    ]  # limpets are not traded
    assert catalogue.source.repository == "EDCD/FDevIDs"
    assert len(catalogue.source.commit) == 40


@pytest.mark.parametrize(
    "rare",
    [
        RARE + "1,Gold,1,Metals,Gold\n",  # listed twice
        RARE + "1,Ghost,1,,Ghost\n",  # no category
    ],
)
def test_what_the_script_cannot_take_is_refused(tmp_path: Path, rare: str) -> None:
    output = tmp_path / "commodities.json"
    files = {"commodity.csv": COMMON, "rare_commodity.csv": rare}
    assert importer.main(["import", str(output)], read(files)) == 1
    assert not output.exists()


def test_usage() -> None:
    assert importer.main(["import", "a", "b"]) == 2
