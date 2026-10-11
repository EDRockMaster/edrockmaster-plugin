"""A small engineering catalogue, shaped like catalogue.json, for the domain tests."""

from typing import Any

from edrockmaster.domain.engineering.catalogue import Catalogue

DATA: dict[str, Any] = {
    "format": 6,
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
    "on_foot_materials": {
        "chemicalsample": {"kind": "item", "name": "Chemical Sample"},
        "graphene": {"kind": "component", "name": "Graphene"},
        "healthpack": {"kind": "consumable", "name": "Medkit"},
        "internalcorrespondence": {"kind": "data", "name": "Internal Correspondence"},
    },
    "on_foot_engineers": {"400002": "Domino Green", "400004": "Kit Fowler"},
    "on_foot_items": {
        "flightsuit": {"kind": "suit", "name": "Flight suit", "upgrades": {}},
        "tacticalsuit": {
            "kind": "suit",
            "name": "Dominator suit",
            "upgrades": {
                "2": {
                    "credits": 600000,
                    "ingredients": {"chemicalsample": 1, "graphene": 2},
                    "confidence": "game",
                },
                "3": {
                    "credits": 2250000,
                    "ingredients": {"chemicalsample": 2, "graphene": 5},
                    "confidence": "deduced",
                },
            },
        },
    },
    "on_foot_modifications": {
        "suit_backpackcapacity": {
            "kind": "suit",
            "name": "Extra backpack capacity",
            "engineers": [400002],
            "recipes": [
                {
                    "items": ["tacticalsuit"],
                    "credits": 750000,
                    "ingredients": {"graphene": 3, "internalcorrespondence": 5},
                    "confidence": "game",
                }
            ],
        },
        "weapon_handling": {
            "kind": "weapon",
            "name": "Faster handling",
            "engineers": [],
            "recipes": [],
        },
    },
    "engineer_details": {
        "300100": {
            "system": "Deciat",
            "base": "Farseer Inc",
            "referred_by": [],
            "invitation": "Reach the exploration rank of Scout.",
            "unlock": "Deliver 1 Meta-Alloys.",
            "referral": None,
            "unlock_gives": {},
            "referral_gives": {},
            "confidence": "web",
        },
        "400002": {
            "system": "Orishis",
            "base": "The Jackrabbit",
            "referred_by": [300100],
            "invitation": None,
            "unlock": "Travel at least 100 ly in shuttles.",
            "referral": "Give 5 Push.",
            "unlock_gives": {"internalcorrespondence": 2},
            "referral_gives": {"chemicalsample": 5},
            "confidence": "game",
        },
        "400004": {
            "system": "Capoya",
            "base": "The Last Call",
            "referred_by": [400002],
            "invitation": None,
            "unlock": "Sell 3 Graphene.",
            "referral": None,
            "unlock_gives": {"graphene": 3},
            "referral_gives": {},
            "confidence": "web",
        },
    },
}


def catalogue() -> Catalogue:
    return Catalogue.from_data(DATA)
