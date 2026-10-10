import copy
from typing import Any

import pytest

from edrockmaster.domain.engineering.catalogue import (
    Catalogue,
    CatalogueError,
    EquipmentKind,
    MaterialCategory,
    OnFootKind,
    RecipeConfidence,
)
from tests.domain.engineering.catalogue_data import DATA


def changed(path: tuple[str, ...], value: object) -> dict[str, Any]:
    data = copy.deepcopy(DATA)
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return data


def test_a_catalogue_is_read_with_its_journal_names() -> None:
    catalogue = Catalogue.from_data(DATA)
    arsenic = catalogue.materials["arsenic"]
    assert arsenic.category is MaterialCategory.RAW
    assert arsenic.grade == 2
    blueprint = catalogue.blueprints["FSD_LongRange"]
    assert blueprint.english_name == "Increased range"
    assert blueprint.grades[5] == {"arsenic": 1, "chemicalmanipulators": 1, "dataminedwake": 1}
    assert catalogue.effects["special_fsd_heavy"].ingredients == {"arsenic": 5, "dataminedwake": 3}
    assert catalogue.engineers == {300100: "Felicity Farseer"}


def test_a_catalogue_has_the_on_foot_materials_and_engineers() -> None:
    catalogue = Catalogue.from_data(DATA)
    sample = catalogue.on_foot_materials["chemicalsample"]
    assert (sample.kind, sample.english_name) == (OnFootKind.ITEM, "Chemical Sample")
    assert catalogue.on_foot_materials["internalcorrespondence"].kind is OnFootKind.DATA
    assert catalogue.on_foot_engineers == {400002: "Domino Green"}
    # The ship engineers stay apart: the engineering view lists them on their own
    assert 400002 not in catalogue.engineers


def test_a_catalogue_has_the_class_upgrades_of_suits_and_weapons() -> None:
    items = Catalogue.from_data(DATA).on_foot_items
    dominator = items["tacticalsuit"]
    assert (dominator.kind, dominator.english_name) == (EquipmentKind.SUIT, "Dominator suit")
    upgrade = dominator.upgrades[3]
    assert upgrade.to_class == 3
    assert upgrade.credits == 2250000
    assert upgrade.ingredients == {"chemicalsample": 2, "graphene": 5}
    # Deduced from a rule read in game, not seen itself (ADR 0030)
    assert upgrade.confidence is RecipeConfidence.DEDUCED
    assert dominator.upgrades[2].confidence is RecipeConfidence.GAME
    # Unknown recipes are absent; the flight suit has no class at all
    assert 4 not in dominator.upgrades
    assert items["flightsuit"].upgrades == {}


def test_the_engineers_offering_a_grade_depend_on_the_module() -> None:
    fsd = Catalogue.from_data(DATA).modules["fsd"]
    assert fsd.engineers("FSD_LongRange", 5) == (300100,)
    assert fsd.engineers("FSD_LongRange", 4) == ()
    assert fsd.engineers("Engine_Dirty", 5) == ()
    assert fsd.effects == ("special_fsd_heavy",)


@pytest.mark.parametrize(("grade", "cap"), [(1, 300), (2, 250), (3, 200), (4, 150), (5, 100)])
def test_the_cap_of_a_material_depends_on_its_grade(grade: int, cap: int) -> None:
    data = changed(("materials", "arsenic", "grade"), grade)
    assert Catalogue.from_data(data).materials["arsenic"].cap == cap


def test_the_date_of_the_data_is_the_most_recent_source() -> None:
    assert Catalogue.from_data(DATA).date == "2026-09-05"


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("format",), 1, "format"),
        (("on_foot_materials", "graphene", "kind"), "gadget", "malformed"),
        (("on_foot_engineers",), None, "malformed"),
        (("materials", "arsenic", "grade"), 6, "grade 6"),
        (("materials", "arsenic", "category"), "odyssey", "malformed"),
        (("blueprints", "FSD_LongRange", "grades"), {"6": {"arsenic": 1}}, "grade 6"),
        (("blueprints", "FSD_LongRange", "grades"), {"5": {"iron": 1}}, "'iron'"),
        (("effects", "special_fsd_heavy", "ingredients"), {"arsenic": 0}, "0 arsenic"),
        (("modules", "fsd", "blueprints"), {"Engine_Dirty": {}}, "'Engine_Dirty'"),
        (("modules", "fsd", "blueprints"), {"FSD_LongRange": {"5": [1]}}, "unknown engineers"),
        (("modules", "fsd", "effects"), ["special_unknown"], "'special_unknown'"),
        (("engineers",), None, "malformed"),
        (("on_foot_items", "tacticalsuit", "kind"), "helmet", "malformed"),
        (("on_foot_items", "tacticalsuit", "upgrades", "3", "confidence"), "rumour", "malformed"),
        (("on_foot_items", "tacticalsuit", "upgrades", "2", "credits"), "a lot", "malformed"),
        (
            ("on_foot_items", "tacticalsuit", "upgrades", "6"),
            {"credits": 1, "ingredients": {"graphene": 1}, "confidence": "game"},
            "class 6",
        ),
        (("on_foot_items", "tacticalsuit", "upgrades", "2", "credits"), 0, "0 credits"),
        (("on_foot_items", "tacticalsuit", "upgrades", "2", "ingredients"), {"iron": 1}, "'iron'"),
        (
            ("on_foot_items", "tacticalsuit", "upgrades", "2", "ingredients"),
            {"healthpack": 1},
            "consumable 'healthpack'",
        ),
        (
            ("on_foot_items", "tacticalsuit", "upgrades", "2", "ingredients"),
            {"graphene": 0},
            "0 graphene",
        ),
    ],
)
def test_a_catalogue_the_code_does_not_expect_is_refused(
    path: tuple[str, ...], value: object, message: str
) -> None:
    with pytest.raises(CatalogueError, match=message):
        Catalogue.from_data(changed(path, value))


@pytest.mark.parametrize(
    ("item", "module"),
    [
        ("int_hyperdrive_size5_class5", "fsd"),
        ("Int_Hyperdrive_Size5_Class5", "fsd"),
        ("anaconda_armour_grade3", "bh"),
        ("sidewinder_armour_reactive", "bh"),
        ("int_cargorack_size2_class1", None),
    ],
)
def test_the_module_type_of_an_item(item: str, module: str | None) -> None:
    found = Catalogue.from_data(DATA).module_of(item)
    assert (found.key if found else None) == module
