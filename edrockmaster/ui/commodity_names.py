"""Display names of the commodities the plugin knows before the journal names them."""

from __future__ import annotations

from collections.abc import Callable

from edrockmaster.domain.commodities import Commodity

MINEABLE: tuple[tuple[str, str], ...] = (
    ("alexandrite", "Alexandrite"),
    ("benitoite", "Benitoite"),
    ("bromellite", "Bromellite"),
    ("gold", "Gold"),
    ("grandidierite", "Grandidierite"),
    ("lowtemperaturediamond", "Low Temperature Diamonds"),
    ("monazite", "Monazite"),
    ("musgravite", "Musgravite"),
    ("osmium", "Osmium"),
    ("painite", "Painite"),
    ("palladium", "Palladium"),
    ("platinum", "Platinum"),
    ("praseodymium", "Praseodymium"),
    ("rhodplumsite", "Rhodplumsite"),
    ("samarium", "Samarium"),
    ("serendibite", "Serendibite"),
    ("silver", "Silver"),
    ("tritium", "Tritium"),
    ("opal", "Void Opals"),
)
"""Commodity key and English name, for the alert thresholds of the preferences."""

_NAMES = dict(MINEABLE)


def commodity_name(commodity: Commodity, translate: Callable[[str], str]) -> str:
    """The game's own name when the journal gave one, else ours, else the raw key."""
    if commodity.localised:
        return commodity.localised
    name = _NAMES.get(commodity.key)
    return translate(name) if name else commodity.key
