"""The commodities shipped with the application (ADR 0047)."""

import json
from pathlib import Path

import pytest

from edrockmaster.domain.commodities import LIMPET, REFINED_COMMODITIES, Commodity
from edrockmaster.domain.trade.catalogue import CommodityCategory
from edrockmaster.infrastructure.commodity_catalogue_file import load_commodities
from edrockmaster.ui.commodity_names import MINEABLE


def test_the_shipped_catalogue_knows_every_category_and_what_is_mined() -> None:
    catalogue = load_commodities()
    assert len(catalogue) > 400
    assert set(catalogue.by_category()) == set(CommodityCategory)
    assert {commodity.key for commodity in REFINED_COMMODITIES} <= {
        commodity.key for commodity in catalogue.commodities
    }
    assert {key for key, _name in MINEABLE} <= {c.key for c in catalogue.commodities}
    assert catalogue.get("lavianbrandy") is not None
    assert catalogue.get("drones") is None  # limpets are not traded


def test_a_file_that_is_not_a_catalogue_is_refused(tmp_path: Path) -> None:
    broken = tmp_path / "commodities.json"
    broken.write_text(json.dumps({"source": {}, "commodities": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a catalogue"):
        load_commodities(broken)


ROOT = Path(__file__).resolve().parents[2]
JOURNALS = [
    *sorted((ROOT / "tests" / "fixtures").glob("*.jsonl")),
    ROOT / "edrockmaster" / "desktop" / "demo_journal.jsonl",
]
TRADED = {"MarketBuy", "MarketSell", "MiningRefined", "CollectCargo", "EjectCargo"}


def test_every_commodity_the_recorded_journals_trade_is_known() -> None:
    catalogue = load_commodities()
    named = {
        Commodity.from_symbol(entry["Type"]).key
        for path in JOURNALS
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for entry in (json.loads(line),)
        if entry.get("event") in TRADED
    }
    assert named
    assert named - {LIMPET.key} <= {commodity.key for commodity in catalogue.commodities}
