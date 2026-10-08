"""The live view, as its schema describes it (ADR 0020, ADR 0023)."""

import json
from pathlib import Path

import jsonschema

from edrockmaster.desktop.live_view import SCHEMA, live_view
from edrockmaster.domain.situation.journal import GameMode, Ship
from edrockmaster.domain.situation.situation import Situation

VALIDATOR = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


def view(situation: Situation) -> dict[str, object]:
    built = live_view(
        language="fr",
        current="mining",
        blocks=(),
        notice=None,
        journal_folder=Path("journal"),
        journal_file=None,
        situation=situation,
    )
    VALIDATOR.validate(built)
    return built


def test_the_situation_in_the_view() -> None:
    built = view(
        Situation(
            commander="Nyx-Vela",
            ship=Ship("mamba", "Mamba", "Rocky", "RM-01"),
            system="Sol",
            station="Abraham Lincoln",
            mode=GameMode.GROUP,
            group="Nyx-Vela",
            wing=("Cmdr A",),
            game_running=True,
        )
    )
    assert built["situation"] == {
        "commander": "Nyx-Vela",
        "ship": {"type": "Mamba", "name": "Rocky", "ident": "RM-01"},
        "onFoot": False,
        "system": "Sol",
        "station": "Abraham Lincoln",
        "mode": "group",
        "group": "Nyx-Vela",
        "wing": ["Cmdr A"],
        "gameRunning": True,
    }


def test_a_ship_type_never_named_shows_its_symbol() -> None:
    built = view(Situation(ship=Ship("PantherMkII")))
    assert built["situation"]["ship"] == {"type": "PantherMkII", "name": None, "ident": None}  # type: ignore[index]


def test_an_unknown_situation() -> None:
    situation = view(Situation())["situation"]
    assert situation["ship"] is None  # type: ignore[index]
    assert situation["mode"] is None  # type: ignore[index]
