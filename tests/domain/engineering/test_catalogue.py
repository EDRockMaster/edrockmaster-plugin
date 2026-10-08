import copy
from typing import Any

import pytest

from edrockmaster.domain.engineering.catalogue import (
    Catalogue,
    CatalogueError,
    MaterialCategory,
)

DATA: dict[str, Any] = {
    "format": 1,
    "sources": [
        {"repository": "EDCD/FDevIDs", "commit": "c356", "date": "2026-09-05"},
        {"repository": "EDCD/coriolis-data", "commit": "0db9", "date": "2026-04-24"},
    ],
    "materials": {
        "arsenic": {"category": "raw", "grade": 2, "name": "Arsenic"},
        "chemicalmanipulators": {
            "category": "manufactured",
            "grade": 4,
            "name": "Chemical Manipulators",
        },
        "dataminedwake": {"category": "encoded", "grade": 5, "name": "Datamined Wake Exceptions"},
    },
    "engineers": {"300100": "Felicity Farseer"},
    "blueprints": {
        "FSD_LongRange": {
            "name": "Increased range",
            "grades": {"5": {"arsenic": 1, "chemicalmanipulators": 1, "dataminedwake": 1}},
        }
    },
    "effects": {
        "special_fsd_heavy": {
            "name": "Mass Manager",
            "ingredients": {"arsenic": 5, "dataminedwake": 3},
        }
    },
    "modules": {
        "fsd": {
            "name": "Frame shift drive",
            "blueprints": {"FSD_LongRange": {"5": [300100]}},
            "effects": ["special_fsd_heavy"],
        }
    },
}


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
        (("format",), 2, "format"),
        (("materials", "arsenic", "grade"), 6, "grade 6"),
        (("materials", "arsenic", "category"), "odyssey", "malformed"),
        (("blueprints", "FSD_LongRange", "grades"), {"6": {"arsenic": 1}}, "grade 6"),
        (("blueprints", "FSD_LongRange", "grades"), {"5": {"iron": 1}}, "'iron'"),
        (("effects", "special_fsd_heavy", "ingredients"), {"arsenic": 0}, "0 arsenic"),
        (("modules", "fsd", "blueprints"), {"Engine_Dirty": {}}, "'Engine_Dirty'"),
        (("modules", "fsd", "blueprints"), {"FSD_LongRange": {"5": [1]}}, "unknown engineers"),
        (("modules", "fsd", "effects"), ["special_unknown"], "'special_unknown'"),
        (("engineers",), None, "malformed"),
    ],
)
def test_a_catalogue_the_code_does_not_expect_is_refused(
    path: tuple[str, ...], value: object, message: str
) -> None:
    with pytest.raises(CatalogueError, match=message):
        Catalogue.from_data(changed(path, value))
