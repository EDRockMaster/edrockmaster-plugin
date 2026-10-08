"""A small engineering catalogue, shaped like catalogue.json, for the domain tests."""

from typing import Any

from edrockmaster.domain.engineering.catalogue import Catalogue

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
            "items": ["int_hyperdrive_size5_class5", "int_hyperdrive_overcharge_size5_class5"],
        },
        "bh": {"name": "Armour", "blueprints": {}, "effects": [], "items": []},
    },
}


def catalogue() -> Catalogue:
    return Catalogue.from_data(DATA)
