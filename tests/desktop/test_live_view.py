"""The live view, as its schema describes it (ADR 0020, ADR 0023)."""

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import jsonschema

from edrockmaster.application.activity import Activity
from edrockmaster.application.updates import UpdateReady
from edrockmaster.desktop.live_view import live_view
from edrockmaster.domain.situation.journal import GameMode, RouteStop, Ship
from edrockmaster.domain.situation.route import CurrentRoute
from edrockmaster.domain.situation.situation import Situation
from edrockmaster.ui.panel_model import ActivityBlock, PanelModel, StatLine
from tests.desktop.schemas import LIVE_VIEW_SCHEMA as SCHEMA

EMPTY_ENGINEERING: dict[str, object] = {
    "inventoryKnown": False,
    "materials": [],
    "engineers": [],
    "goals": [],
    "shoppingList": [],
    "unlocks": [],
    "priority": [],
    "catalogueDate": "2026-09-05",
    "onFoot": {
        "known": False,
        "materials": [],
        "engineers": [],
        "equipment": [],
        "carrierMoves": [],
        "goals": [],
        "modifications": [],
        "shoppingList": [],
        "credits": 0,
        "unlocks": [],
    },
}
VALIDATOR = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


def view(
    situation: Situation,
    blocks: tuple[ActivityBlock, ...] = (),
    update: UpdateReady | None = None,
) -> dict[str, object]:
    built = live_view(
        language="fr",
        current="mining",
        blocks=blocks,
        notice=None,
        update=update,
        journal_folder=Path("journal"),
        journal_file=None,
        situation=situation,
        engineering=EMPTY_ENGINEERING,
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
        "route": None,
    }


def test_a_ship_type_never_named_shows_its_symbol() -> None:
    built = view(Situation(ship=Ship("PantherMkII")))
    assert built["situation"]["ship"] == {"type": "PantherMkII", "name": None, "ident": None}  # type: ignore[index]


def test_an_unknown_situation() -> None:
    situation = view(Situation())["situation"]
    assert situation["ship"] is None  # type: ignore[index]
    assert situation["mode"] is None  # type: ignore[index]


def test_the_version_is_left_to_the_window_s_title_bar() -> None:
    # The title bar shows it (desktop/window.py); the page does not repeat it
    assert "application" not in view(Situation())


def test_a_line_counts_down_to_its_moment_in_utc() -> None:
    # A community goal's expiry (ADR 0032): the interface counts it down
    paris = timezone(timedelta(hours=2))
    lines = (
        StatLine(
            "Satellite launch, HIP 74116", "1,240", until=datetime(2026, 10, 15, 9, 0, tzinfo=paris)
        ),
        StatLine("Raw gained", "2"),
    )
    model = PanelModel("Goals joined: 1", lines, None, False)
    built = view(Situation(), (ActivityBlock(Activity.COMMUNITY_GOALS, model),))
    activities = built["activities"]
    assert isinstance(activities, list)
    [block] = activities
    assert block["activity"] == "communityGoals"
    assert block["lines"] == [
        {"label": "Satellite launch, HIP 74116", "value": "1,240", "until": "2026-10-15T07:00:00Z"},
        {"label": "Raw gained", "value": "2"},
    ]
    assert datetime.fromisoformat(block["lines"][0]["until"]).tzinfo == UTC


def test_the_route_in_the_view() -> None:
    stops = (RouteStop("Sol", "G"), RouteStop("Sirius B", "DA"), RouteStop("Procyon", "F"))
    route = CurrentRoute(stops, 0, stops[1], 2, fuel_level=30.0)
    built = view(Situation(system="Sol", route=route))
    assert built["situation"]["route"] == {  # type: ignore[index]
        "destination": "Procyon",
        "jumpsLeft": 2,
        "offRoute": False,
        "next": {
            "system": "Sirius B",
            "starClass": "DA",
            "scoopable": False,
            "danger": "whiteDwarf",
        },
        "nextScoopableIn": 2,
        "fuelTight": False,
    }


def test_a_route_off_its_list() -> None:
    route = CurrentRoute((RouteStop("Sol", "G"), RouteStop("Procyon", "F")), None, None, 1, True)
    shown = view(Situation(route=route))["situation"]["route"]  # type: ignore[index]
    assert (shown["offRoute"], shown["next"], shown["nextScoopableIn"]) == (True, None, None)


def test_a_version_ready_in_the_view() -> None:
    assert view(Situation())["update"] is None
    assert view(Situation(), update=UpdateReady("0.7.1"))["update"] == {"version": "0.7.1"}
