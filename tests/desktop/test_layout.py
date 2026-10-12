"""The order of the cards and those folded, kept between sessions (ADR 0021)."""

import json
from typing import Any

import jsonschema
import pytest

from edrockmaster.desktop.layout import (
    CARDS,
    KEY_LAYOUT,
    LayoutError,
    LayoutStore,
    ViewLayout,
    layout_view,
    view_layout_from_request,
)
from tests.desktop.schemas import LIVE_VIEW_SCHEMA as SCHEMA
from tests.fakes import FakeConfig

SCHEMAS = SCHEMA.parent


def first_layout() -> dict[str, ViewLayout]:
    """The layout before the player changes it: each view's cards in their first order."""
    return {view: ViewLayout(cards, frozenset()) for view, cards in CARDS.items()}


def test_the_cards_of_each_view_in_their_first_order() -> None:
    assert CARDS["activities"] == ("mining", "combat", "trade", "engineering", "communityGoals")
    assert CARDS["engineering"] == ("goals", "shopping", "inventory", "engineers")
    assert CARDS["onFoot"] == (
        "goals",
        "shopping",
        "inventory",
        "carrier",
        "equipment",
        "engineers",
    )
    assert LayoutStore(FakeConfig()).load()["engineering"] == ViewLayout(
        CARDS["engineering"], frozenset()
    )


def test_the_view_gives_every_card_of_every_view() -> None:
    layout = first_layout()
    layout["engineering"] = ViewLayout(
        ("inventory", "goals", "shopping", "engineers"), frozenset({"engineers"})
    )
    view = layout_view(layout)
    assert view["engineering"] == {
        "order": ["inventory", "goals", "shopping", "engineers"],
        "folded": ["engineers"],
    }
    assert view["activities"]["order"] == list(CARDS["activities"])
    schema = json.loads((SCHEMAS / "layout.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(view)


def test_a_request_completes_the_order_with_the_cards_it_leaves_out() -> None:
    request = {"order": ["inventory", "goals"], "folded": ["inventory"]}
    assert view_layout_from_request("engineering", request) == ViewLayout(
        ("inventory", "goals", "shopping", "engineers"), frozenset({"inventory"})
    )


@pytest.mark.parametrize(
    ("view", "request_", "message"),
    [
        ("blueprints", {"order": [], "folded": []}, "view"),
        ("engineering", {"order": ["goals", "goals"], "folded": []}, "twice"),
        ("engineering", {"order": ["helmet"], "folded": []}, "'helmet'"),
        ("engineering", {"order": "goals", "folded": []}, "order"),
        ("engineering", {"order": [], "folded": ["helmet"]}, "'helmet'"),
        ("engineering", {"order": [], "folded": None}, "folded"),
        ("engineering", {"order": [3], "folded": []}, "3"),
    ],
)
def test_a_request_the_interface_cannot_send_is_refused(
    view: str, request_: dict[str, Any], message: str
) -> None:
    with pytest.raises(LayoutError, match=message):
        view_layout_from_request(view, request_)


def test_the_layout_is_kept_in_the_settings_file() -> None:
    config = FakeConfig()
    store = LayoutStore(config)
    assert store.load() == first_layout()
    layout = first_layout()
    layout["onFoot"] = ViewLayout(
        ("engineers", *CARDS["onFoot"][:-1]), frozenset({"carrier", "equipment"})
    )
    store.save(layout)
    assert json.loads(str(config.values[KEY_LAYOUT]))["onFoot"]["folded"] == [
        "carrier",
        "equipment",
    ]
    assert store.load() == layout


@pytest.mark.parametrize(
    "stored",
    [
        "not json",
        "[]",
        json.dumps({"activities": "mining"}),
        json.dumps({"engineering": {"order": ["helmet", "goals"], "folded": ["helmet"]}}),
    ],
)
def test_a_layout_stored_wrong_falls_back_to_what_it_can(stored: str) -> None:
    store = LayoutStore(FakeConfig({KEY_LAYOUT: stored}))
    layout = store.load()
    assert set(layout) == set(CARDS)
    # What is known is kept, the rest falls back to the first order
    assert layout["engineering"].order[0] == "goals"
    assert layout["engineering"].folded == frozenset()
