import json
from pathlib import Path

from edrockmaster.domain.ships import PadSize, needed_pad

SHIP_NAMES = Path(__file__).resolve().parents[2] / "edrockmaster/domain/situation/ship_names.json"


def test_pad_sizes_by_their_number_and_what_fits() -> None:
    assert PadSize.from_number(1) is PadSize.SMALL
    assert PadSize.from_number(3) is PadSize.LARGE
    assert PadSize.from_number(None) is None
    assert PadSize.from_number(9) is None
    assert PadSize.LARGE.fits(PadSize.MEDIUM)
    assert not PadSize.MEDIUM.fits(PadSize.LARGE)


def test_the_pad_each_ship_needs() -> None:
    assert needed_pad("anaconda") is PadSize.LARGE
    assert needed_pad("Python") is PadSize.MEDIUM
    assert needed_pad("cobramkiii") is PadSize.SMALL
    assert needed_pad("type9_military") is PadSize.LARGE
    assert needed_pad("unknown_ship") is None


def test_every_ship_the_application_names_has_its_pad() -> None:
    symbols = json.loads(SHIP_NAMES.read_text(encoding="utf-8"))
    assert [symbol for symbol in symbols if needed_pad(symbol) is None] == []
