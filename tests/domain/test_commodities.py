import pytest

from edrockmaster.domain.commodities import Commodity


@pytest.mark.parametrize(
    ("symbol", "key"),
    [
        ("$painite_name;", "painite"),
        ("Painite", "painite"),
        ("$LowTemperatureDiamond_name;", "lowtemperaturediamond"),
        ("lowtemperaturediamond", "lowtemperaturediamond"),
        ("  $Platinum_Name;  ", "platinum"),
    ],
)
def test_symbol_is_normalised_to_a_stable_key(symbol: str, key: str) -> None:
    assert Commodity.from_symbol(symbol).key == key


def test_same_commodity_from_different_symbols_is_equal() -> None:
    assert Commodity.from_symbol("$painite_name;") == Commodity.from_symbol("Painite")


def test_localised_name_is_kept_but_not_part_of_identity() -> None:
    localised = Commodity.from_symbol("$painite_name;", localised="Painite (FR)")
    assert localised.display_name == "Painite (FR)"
    assert localised == Commodity.from_symbol("painite")


def test_display_name_falls_back_to_the_key() -> None:
    assert Commodity.from_symbol("$bromellite_name;").display_name == "bromellite"


def test_empty_symbol_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        Commodity.from_symbol("  ")
