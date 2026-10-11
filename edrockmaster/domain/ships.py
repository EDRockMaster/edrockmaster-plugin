"""Ships, as far as landing goes: the pad each type needs."""

from __future__ import annotations

from enum import Enum


class PadSize(Enum):
    """A landing pad, small to large."""

    SMALL = 1
    MEDIUM = 2
    LARGE = 3

    @classmethod
    def from_number(cls, number: int | None) -> PadSize | None:
        try:
            return cls(number) if number is not None else None
        except ValueError:
            return None

    def fits(self, needed: PadSize) -> bool:
        """Whether a ship that needs ``needed`` can land on this pad."""
        return self.value >= needed.value


_SMALL = (
    "adder", "cobramkiii", "cobramkiv", "cobramkv", "diamondback", "diamondbackxl", "dolphin",
    "eagle", "empire_courier", "empire_eagle", "hauler", "sidewinder", "smallcombat01_nx",
    "viper", "viper_mkiv", "vulture",
)  # fmt: skip
_MEDIUM = (
    "asp", "asp_scout", "corsair", "federation_dropship", "federation_dropship_mkii",
    "federation_gunship", "ferdelance", "independant_trader", "krait_light", "krait_mkii",
    "lakonminer", "mamba", "mandalay", "mediumtransport01", "python", "python_nx", "type6",
    "type8", "typex", "typex_2", "typex_3",
)  # fmt: skip
_LARGE = (
    "anaconda", "belugaliner", "cutter", "empire_trader", "explorer_nx", "federation_corvette",
    "orca", "panthermkii", "type7", "type9", "type9_military",
)  # fmt: skip

_PADS: dict[str, PadSize] = {
    **dict.fromkeys(_SMALL, PadSize.SMALL),
    **dict.fromkeys(_MEDIUM, PadSize.MEDIUM),
    **dict.fromkeys(_LARGE, PadSize.LARGE),
}


def needed_pad(ship_symbol: str) -> PadSize | None:
    """The pad a ship type needs, by its journal symbol; ``None`` for a type not known."""
    return _PADS.get(ship_symbol.strip().lower())
