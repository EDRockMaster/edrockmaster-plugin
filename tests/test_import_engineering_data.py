"""scripts/import_engineering_data.py on small sources shaped like FDevIDs and coriolis-data."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from edrockmaster.domain.engineering.catalogue import Catalogue
from tests.scripts import load_script

importer = load_script("import_engineering_data")

MATERIALS = """id,symbol,rarity,type,category,name
128672128,Arsenic,2,Raw,2,Arsenic
128673867,ChemicalManipulators,4,Manufactured,Chemical,Chemical Manipulators
128681627,ShieldDensityReports,3,Encoded,Shield Data,Untypical Shield Scans{trailing}
128681635,AdaptiveEncryptors,5,Encoded,Encryption Files,Adaptive Encryptors Capture
""".format(trailing=" ")  # FDevIDs has this trailing space
ENGINEERS = """id,system_address,market_id,name
300100,6681123623626,128676487,Felicity Farseer
300260,3107576681170,128680583,Tod 'The Blaster' McQuinn
300000,3932277478114,128673927,Didi Vatermann
"""
BLUEPRINTS: dict[str, Any] = {
    "FSD_LongRange": {
        "fdname": "FSD_LongRange",
        "name": "Increased range",
        "grades": {
            "5": {"components": {"Arsenic": 1, "Chemical Manipulators": 1}},
            "1": {"components": {"Untypical Shield Scans": 1}},
        },
    },
    "Unused": {"fdname": "Unused", "name": "Unused", "grades": {}},
}
MODULES: dict[str, Any] = {
    "fsd": {
        "blueprints": {
            "FSD_LongRange": {
                "grades": {
                    "5": {"engineers": ["Felicty Farseer"]},
                    "1": {"engineers": ['Tod "The Blaster" McQuinn', "Felicity Farseer"]},
                }
            }
        },
        "specials": ["special_fsd_heavy", "special_legacy"],
    },
    "mr": {"blueprints": {}, "specials_D": ["special_fsd_heavy"]},
}
EFFECTS: dict[str, Any] = {
    "special_fsd_heavy": {
        "name": "Mass Manager",
        "components": {"Adaptive Encyptors Capture": 1, "Arsenic": 5},
    },
    "special_legacy": {"name": "Plasma Slug (Legacy)"},
}


MODULE_INDEX = """module.exports = {
  standard: {
    fsd: require('./standard/frame_shift_drive').fsd,
    pd: require('./standard/power_distributor').pd,
  },
};
"""
FSD_ITEMS: dict[str, Any] = {
    "fsd": [
        {"grp": "fsd", "symbol": "Int_Hyperdrive_Size5_Class5"},
        {"grp": "fsd", "symbol": "Int_Hyperdrive_Size2_Class1"},
        {"grp": "gfsb", "symbol": "Int_GuardianFSDBooster_Size1"},
    ]
}


class Sources:
    def __init__(self) -> None:
        self.files = {
            "material.csv": MATERIALS,
            "engineers.csv": ENGINEERS,
            "modifications/blueprints.json": json.dumps(BLUEPRINTS),
            "modifications/modules.json": json.dumps(MODULES),
            "modifications/specials.json": json.dumps(EFFECTS),
            "modules/index.js": MODULE_INDEX,
            "modules/standard/frame_shift_drive.json": json.dumps(FSD_ITEMS),
        }
        self.read_at: set[tuple[str, str]] = set()

    def read(self, source: Any, path: str) -> str:
        self.read_at.add((source.repository, source.commit))
        return self.files[path]

    def change(self, path: str, edit: Any) -> None:
        data = json.loads(self.files[path])
        edit(data)
        self.files[path] = json.dumps(data)


@pytest.fixture
def sources() -> Sources:
    return Sources()


def test_the_catalogue_keeps_what_the_plugin_uses(sources: Sources) -> None:
    catalogue = importer.build_catalogue(sources.read)
    assert catalogue["materials"]["arsenic"] == {"category": "raw", "grade": 2, "name": "Arsenic"}
    assert catalogue["blueprints"] == {
        "FSD_LongRange": {
            "name": "Increased range",
            "grades": {
                "1": {"shielddensityreports": 1},
                "5": {"arsenic": 1, "chemicalmanipulators": 1},
            },
        }
    }
    assert catalogue["modules"] == {
        "fsd": {
            "name": "Frame shift drive",
            "blueprints": {"FSD_LongRange": {"1": [300100, 300260], "5": [300100]}},
            "effects": ["special_fsd_heavy"],
            "items": ["int_hyperdrive_size2_class1", "int_hyperdrive_size5_class5"],
        }
    }
    assert catalogue["effects"] == {
        "special_fsd_heavy": {
            "name": "Mass Manager",
            "ingredients": {"adaptiveencryptors": 1, "arsenic": 5},
        }
    }
    # Only the engineers offering a ship blueprint
    assert catalogue["engineers"] == {
        "300100": "Felicity Farseer",
        "300260": "Tod 'The Blaster' McQuinn",
    }
    Catalogue.from_data(catalogue)


def test_the_sources_are_read_at_their_pinned_commits(sources: Sources) -> None:
    catalogue = importer.build_catalogue(sources.read)
    assert sources.read_at == {
        ("EDCD/FDevIDs", importer.FDEVIDS.commit),
        ("EDCD/coriolis-data", importer.CORIOLIS.commit),
    }
    assert catalogue["sources"][0] == {
        "repository": "EDCD/FDevIDs",
        "commit": importer.FDEVIDS.commit,
        "date": importer.FDEVIDS.date,
    }


@pytest.mark.parametrize(
    ("path", "edit", "message"),
    [
        (
            "modifications/specials.json",
            lambda data: data["special_fsd_heavy"]["components"].update({"Unobtainium": 1}),
            "ingredient 'Unobtainium'",
        ),
        (
            "modifications/modules.json",
            lambda data: data["fsd"]["blueprints"]["FSD_LongRange"]["grades"]["5"].update(
                {"engineers": ["Nobody"]}
            ),
            "engineer 'Nobody'",
        ),
        (
            "modifications/modules.json",
            lambda data: data.update({"zz": copy.deepcopy(data["fsd"])}),
            "module 'zz' has no name",
        ),
        (
            "modifications/modules.json",
            lambda data: data["fsd"]["blueprints"].update({"Missing": {"grades": {}}}),
            "unknown blueprint 'Missing'",
        ),
        (
            "modifications/modules.json",
            lambda data: data["fsd"]["specials"].append("special_missing"),
            "unknown effect 'special_missing'",
        ),
    ],
)
def test_a_name_it_cannot_map_is_refused(
    sources: Sources, path: str, edit: Any, message: str
) -> None:
    sources.change(path, edit)
    with pytest.raises(importer.ImportRefused, match=message):
        importer.build_catalogue(sources.read)


def test_the_file_is_stable_and_has_one_entry_per_line(sources: Sources, tmp_path: Path) -> None:
    output = tmp_path / "catalogue.json"
    assert importer.main(["import", str(output)], sources.read) == 0
    text = output.read_text(encoding="utf-8")
    assert json.loads(text) == importer.build_catalogue(sources.read)
    assert '    "FSD_LongRange": {"name": "Increased range", ' in text
    assert importer.main(["import", str(output)], sources.read) == 0
    assert output.read_text(encoding="utf-8") == text


def test_nothing_is_written_when_refused(
    sources: Sources, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sources.change("modifications/modules.json", lambda data: data.update({"zz": data["fsd"]}))
    output = tmp_path / "catalogue.json"
    assert importer.main(["import", str(output)], sources.read) == 1
    assert not output.exists()
    assert "refused" in capsys.readouterr().err


def test_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert importer.main(["import", "a", "b"]) == 2
    assert "Usage" in capsys.readouterr().err


def test_the_shipped_catalogue_names_every_module_the_script_knows() -> None:
    shipped = json.loads(importer.DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    assert {entry["name"] for entry in shipped["modules"].values()} <= set(
        importer.MODULE_NAMES.values()
    )
    assert shipped["sources"][1]["commit"] == importer.CORIOLIS.commit


def test_a_module_without_items_is_refused(sources: Sources) -> None:
    sources.files["modules/index.js"] = "module.exports = {};\n"
    with pytest.raises(importer.ImportRefused, match="module 'fsd' has no file"):
        importer.build_catalogue(sources.read)
    sources.files["modules/index.js"] = MODULE_INDEX
    sources.files["modules/standard/frame_shift_drive.json"] = json.dumps({"fsd": []})
    with pytest.raises(importer.ImportRefused, match="module 'fsd' has no item"):
        importer.build_catalogue(sources.read)


def test_armour_needs_no_items(sources: Sources) -> None:
    def armour(data: dict[str, Any]) -> None:
        data["bh"] = {"blueprints": copy.deepcopy(data["fsd"]["blueprints"])}

    sources.change("modifications/modules.json", armour)
    assert importer.build_catalogue(sources.read)["modules"]["bh"]["items"] == []
