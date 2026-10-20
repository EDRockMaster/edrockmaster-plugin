"""Reads the commodities shipped with the application (ADR 0047): imported from FDevIDs by
``scripts/import_commodities.py``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from edrockmaster.domain.trade import catalogue as catalogue_module
from edrockmaster.domain.trade.catalogue import (
    CatalogueSource,
    CommodityCatalogue,
    CommodityCategory,
    TradedCommodity,
)

COMMODITIES_FILE = Path(catalogue_module.__file__).with_name("commodities.json")


def load_commodities(path: Path = COMMODITIES_FILE) -> CommodityCatalogue:
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    try:
        source = CatalogueSource(**data["source"])
        return CommodityCatalogue(
            (
                TradedCommodity(
                    key=str(row["key"]),
                    name=str(row["name"]),
                    category=CommodityCategory(row["category"]),
                    rare=bool(row["rare"]),
                )
                for row in data["commodities"]
            ),
            source,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{path} is not a catalogue of commodities: {error}") from error
