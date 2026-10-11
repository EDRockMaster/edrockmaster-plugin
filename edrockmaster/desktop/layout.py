"""The layout of the desktop application's views (ADR 0021): the order of their cards, and
those the player folded.

The *Activities* view and both parts of the *Engineering* view show cards the player can
move and fold. Their layout is kept between sessions in ``settings.json``, beside the other
settings, as one JSON text: ``layout_view`` gives it to the interface, which sends back one
view's layout at a time (``view_layout_from_request``). A card the stored order does not
name (a new one, in a later version) comes after the others, in its first place; a card it
names that no longer exists is dropped.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from edrockmaster.application.activity import Activity
from edrockmaster.infrastructure.settings_store import ConfigStore

KEY_LAYOUT = "edrockmaster.desktop.layout"

CARDS: Mapping[str, tuple[str, ...]] = {
    "activities": tuple(activity.value for activity in Activity),
    "engineering": ("goals", "shopping", "inventory", "engineers"),
    "onFoot": ("goals", "shopping", "inventory", "carrier", "equipment", "engineers"),
}
"""The cards of each view, in their first order."""


class LayoutError(ValueError):
    """The interface sent a layout that is not one of a view's cards."""


@dataclass(frozen=True, slots=True)
class ViewLayout:
    order: tuple[str, ...]
    """Every card of the view, top to bottom."""
    folded: frozenset[str]


type Layout = Mapping[str, ViewLayout]


def default_layout() -> Layout:
    return {view: ViewLayout(cards, frozenset()) for view, cards in CARDS.items()}


def layout_view(layout: Layout) -> dict[str, Any]:
    return {
        view: {"order": list(layout[view].order), "folded": sorted(layout[view].folded)}
        for view in CARDS
    }


def view_layout_from_request(view: str, request: Mapping[str, Any]) -> ViewLayout:
    """One view's layout from the interface; ``LayoutError`` if it is not one of its cards."""
    cards = CARDS.get(view)
    if cards is None:
        raise LayoutError(f"unknown view {view!r}")
    order, folded = request.get("order"), request.get("folded")
    if not isinstance(order, list):
        raise LayoutError(f"{view}: the order is not a list")
    if not isinstance(folded, list):
        raise LayoutError(f"{view}: the folded cards are not a list")
    for card in (*order, *folded):
        if card not in cards:
            raise LayoutError(f"{view}: unknown card {card!r}")
    if len(set(order)) < len(order):
        raise LayoutError(f"{view}: a card is ordered twice")
    return ViewLayout(_complete(cards, order), frozenset(folded))


class LayoutStore:
    """The layout, in ``settings.json``; what it cannot read falls back to the first layout."""

    def __init__(self, config: ConfigStore) -> None:
        self._config = config

    def load(self) -> Layout:
        try:
            stored = json.loads(self._config.get_str(KEY_LAYOUT, default="") or "{}")
        except json.JSONDecodeError:
            stored = {}
        if not isinstance(stored, dict):
            stored = {}
        return {view: _tolerant(cards, stored.get(view)) for view, cards in CARDS.items()}

    def save(self, layout: Layout) -> None:
        self._config.set(KEY_LAYOUT, json.dumps(layout_view(layout), separators=(",", ":")))


def _complete(cards: tuple[str, ...], order: list[Any]) -> tuple[str, ...]:
    named = (card for card in order if isinstance(card, str))
    kept = [card for card in dict.fromkeys(named) if card in cards]
    return (*kept, *(card for card in cards if card not in kept))


def _tolerant(cards: tuple[str, ...], stored: object) -> ViewLayout:
    if not isinstance(stored, dict):
        return ViewLayout(cards, frozenset())
    order, folded = stored.get("order"), stored.get("folded")
    return ViewLayout(
        _complete(cards, order if isinstance(order, list) else []),
        frozenset(card for card in folded if card in cards)
        if isinstance(folded, list)
        else frozenset(),
    )
