"""The catalogue shipped with the plugin, as written by scripts/import_engineering_data.py."""

import pytest

from edrockmaster.domain.engineering.catalogue import Catalogue, MaterialCategory
from edrockmaster.infrastructure.catalogue_file import load_catalogue

FELICITY_FARSEER = 300100


@pytest.fixture(scope="module")
def catalogue() -> Catalogue:
    return load_catalogue()


def test_it_holds_every_ship_material(catalogue: Catalogue) -> None:
    by_category = {
        category: sum(1 for m in catalogue.materials.values() if m.category is category)
        for category in MaterialCategory
    }
    assert by_category == {
        MaterialCategory.RAW: 28,
        MaterialCategory.MANUFACTURED: 64,
        MaterialCategory.ENCODED: 45,
    }


def test_increased_range_grade_5_as_in_game(catalogue: Catalogue) -> None:
    assert catalogue.blueprints["FSD_LongRange"].grades[5] == {
        "arsenic": 1,
        "chemicalmanipulators": 1,
        "dataminedwake": 1,
    }
    fsd = catalogue.modules["fsd"]
    assert FELICITY_FARSEER in fsd.engineers("FSD_LongRange", 5)
    assert catalogue.engineers[FELICITY_FARSEER] == "Felicity Farseer"
    assert "special_fsd_heavy" in fsd.effects


def test_names_the_import_had_to_fix(catalogue: Catalogue) -> None:
    # "Untypical Shield Scans " has a trailing space in FDevIDs; coriolis-data misspells the other
    assert catalogue.materials["shielddensityreports"].english_name == "Untypical Shield Scans"
    assert catalogue.materials["adaptiveencryptors"].english_name == "Adaptive Encryptors Capture"
    assert "Tod 'The Blaster' McQuinn" in catalogue.engineers.values()


def test_legacy_effects_are_left_out(catalogue: Catalogue) -> None:
    assert "special_plasma_slug" not in catalogue.effects


def test_it_states_its_sources(catalogue: Catalogue) -> None:
    assert [source.repository for source in catalogue.sources] == [
        "EDCD/FDevIDs",
        "EDCD/coriolis-data",
    ]
    assert all(len(source.commit) == 40 for source in catalogue.sources)
