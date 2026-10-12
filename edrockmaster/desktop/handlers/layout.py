"""The cards' layout of each view (ADR 0021): kept as the player leaves it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from edrockmaster.desktop.handlers.context import CoreContext
from edrockmaster.desktop.layout import (
    Layout,
    LayoutError,
    LayoutStore,
    layout_view,
    view_layout_from_request,
)


class LayoutHandler:
    def __init__(self, context: CoreContext, store: LayoutStore) -> None:
        self._context = context
        self._store = store
        self._layout: Layout = store.load()

    def layout(self) -> dict[str, Any]:
        """The order of each view's cards, and those folded. The layout is replaced, never
        changed: any thread."""
        return layout_view(self._layout)

    def save_layout(self, view: str, request: Mapping[str, Any]) -> None:
        def save() -> None:
            try:
                changed = view_layout_from_request(view, request)
            except LayoutError as error:
                self._context.logger.warning("Layout refused: %s", error)
                return
            if changed == self._layout[view]:
                return
            self._layout = {**self._layout, view: changed}
            self._store.save(self._layout)

        self._context.on_core(save)
