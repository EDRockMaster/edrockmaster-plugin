"""Commodities as they appear in the game journal."""

from __future__ import annotations

from dataclasses import dataclass, field

_SYMBOL_PREFIX = "$"
_SYMBOL_SUFFIXES = (";", "_name")


@dataclass(frozen=True, slots=True)
class Commodity:
    """A commodity, identified by a stable key whatever the journal spelling.

    The journal names the same commodity ``$painite_name;``, ``Painite`` or
    ``painite`` depending on the event. ``key`` is the normalised form; the
    localised name only serves for display and is not part of the identity.
    """

    key: str
    localised: str | None = field(default=None, compare=False)

    @classmethod
    def from_symbol(cls, symbol: str, localised: str | None = None) -> Commodity:
        key = symbol.strip().lower()
        key = key.removeprefix(_SYMBOL_PREFIX)
        for suffix in _SYMBOL_SUFFIXES:
            key = key.removesuffix(suffix)
        if not key:
            raise ValueError("empty commodity symbol")
        return cls(key=key, localised=localised or None)

    @property
    def display_name(self) -> str:
        return self.localised or self.key


LIMPET = Commodity.from_symbol("drones")

REFINED_COMMODITIES = frozenset(
    Commodity(key)
    for key in (
        # metals
        "aluminium",
        "beryllium",
        "bismuth",
        "cobalt",
        "copper",
        "gallium",
        "gold",
        "indium",
        "lanthanum",
        "lithium",
        "osmium",
        "palladium",
        "platinum",
        "praseodymium",
        "samarium",
        "silver",
        "tantalum",
        "thallium",
        "thorium",
        "titanium",
        "uranium",
        # minerals
        "alexandrite",
        "bauxite",
        "benitoite",
        "bertrandite",
        "bromellite",
        "coltan",
        "cryolite",
        "gallite",
        "goslarite",
        "grandidierite",
        "indite",
        "jadeite",
        "lepidolite",
        "lithiumhydroxide",
        "lowtemperaturediamond",
        "methaneclathrate",
        "methanolmonohydratecrystals",
        "moissanite",
        "monazite",
        "musgravite",
        "opal",
        "painite",
        "pyrophyllite",
        "rhodplumsite",
        "rutile",
        "serendibite",
        "taaffeite",
        "uraninite",
        # chemicals
        "hydrogenperoxide",
        "liquidoxygen",
        "tritium",
        "water",
    )
)
"""Commodities a mining refinery produces. Many are traded too: what tells a mined
ton from a bought one is the price paid, not the commodity."""
