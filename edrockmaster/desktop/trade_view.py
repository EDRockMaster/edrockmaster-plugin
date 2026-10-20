"""The *Trade* tab (ADR 0047): what its forms start from. Where to buy and where to sell are
the market search's, shared with the Mining tab (``market_view.py``).

Names are in the player's language, the commodities of a category sorted by them.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from typing import Any

from edrockmaster.application.settings import SourceSettings
from edrockmaster.desktop.market_view import pad_name
from edrockmaster.domain.ships import PadSize
from edrockmaster.domain.trade.catalogue import CommodityCatalogue

type Translate = Callable[[str], str]


def _sort_key(name: str) -> str:
    """Accents aside, as a reader looks a name up: *Éther* among the E."""
    return "".join(
        letter
        for letter in unicodedata.normalize("NFKD", name.casefold())
        if not unicodedata.combining(letter)
    )


def options_view(  # noqa: PLR0913 - what the forms start from
    catalogue: CommodityCatalogue,
    *,
    system: str | None,
    pad: PadSize | None,
    cargo_capacity: int | None,
    sources: SourceSettings,
    translate: Translate,
) -> dict[str, Any]:
    """The commodities by category, the current system, the ship's pad and cargo capacity."""
    return {
        "categories": [
            {
                "category": category.name.lower(),
                "name": translate(category.value),
                "commodities": sorted(
                    (
                        {
                            "commodity": commodity.key,
                            # As the game names it on a market, not as a material
                            "name": translate(f"{commodity.name}|commodity"),
                            "rare": commodity.rare,
                        }
                        for commodity in commodities
                    ),
                    key=lambda row: _sort_key(str(row["name"])),
                ),
            }
            for category, commodities in catalogue.by_category().items()
        ],
        "system": system,
        "pad": pad_name(pad),
        "cargoCapacity": cargo_capacity,
        "sources": {"ardent": sources.ardent},
    }
