"""The plugin's panel in EDMC's main window (tkinter, main thread only).

It only copies the texts of the presenter's blocks: every decision is the
presenter's. Each activity has its own block (status, reset button, alert,
statistics), created on first display and shown in the order given.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence

from edrockmaster.application.activity import Activity
from edrockmaster.ui.panel_model import ActivityBlock, PanelModel

ALERT_COLOUR = "#ff8c00"
BLOCK_GAP = 6
"""Vertical space above a stacked block, in pixels."""


def _no_theme(_widget: tk.Widget) -> None:
    pass


class Block:
    """One activity's widgets."""

    def __init__(
        self,
        parent: tk.Misc,
        on_reset: Callable[[], None],
        translate: Callable[[str], str],
        theme_update: Callable[[tk.Widget], None],
    ) -> None:
        self._tl = translate
        self._theme_update = theme_update
        self.frame = tk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self._status = tk.Label(self.frame, anchor=tk.W, justify=tk.LEFT)
        self._status.grid(row=0, column=0, sticky=tk.W)
        self._reset = tk.Button(self.frame, command=on_reset)
        self._reset.grid(row=0, column=1, sticky=tk.E)
        # Widgets created in plugin_app() are themed by EDMC; this colour overrides the theme's
        self._alert = tk.Label(
            self.frame, anchor=tk.W, justify=tk.LEFT, foreground=ALERT_COLOUR, font="TkHeadingFont"
        )
        self._alert.grid(row=1, column=0, columnspan=2, sticky=tk.W)
        self._stats = tk.Frame(self.frame)
        self._stats.grid(row=2, column=0, columnspan=2, sticky=tk.EW)
        self._stats.columnconfigure(1, weight=1)
        self._rows: list[tuple[tk.Label, tk.Label]] = []
        self.retranslate()

    def retranslate(self) -> None:
        self._reset["text"] = self._tl("Reset")

    def render(self, model: PanelModel) -> None:
        self._status["text"] = model.status
        self._reset["state"] = tk.NORMAL if model.can_reset else tk.DISABLED
        if model.alert:
            self._alert["text"] = model.alert
            self._alert.grid()
        else:
            self._alert.grid_remove()
        self._ensure_rows(len(model.lines))
        for index, (label, value) in enumerate(self._rows):
            if index < len(model.lines):
                line = model.lines[index]
                label["text"], value["text"] = line.label, line.value
                label.grid()
                value.grid()
            else:
                label.grid_remove()
                value.grid_remove()

    def _ensure_rows(self, count: int) -> None:
        while len(self._rows) < count:
            row = len(self._rows)
            label = tk.Label(self._stats, anchor=tk.W)
            value = tk.Label(self._stats, anchor=tk.E)
            label.grid(row=row, column=0, sticky=tk.W)
            value.grid(row=row, column=1, sticky=tk.E)
            # Created after plugin_app(): EDMC must be asked to theme them
            self._theme_update(label)
            self._theme_update(value)
            self._rows.append((label, value))


class Panel:
    def __init__(
        self,
        parent: tk.Misc,
        on_reset: Callable[[Activity], None],
        translate: Callable[[str], str],
        theme_update: Callable[[tk.Widget], None] = _no_theme,
    ) -> None:
        self._on_reset = on_reset
        self._tl = translate
        self._theme_update = theme_update
        self.frame = tk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self._blocks: dict[Activity, Block] = {}

    def block(self, activity: Activity) -> Block:
        """The block of an activity, created the first time it is needed."""
        if activity not in self._blocks:
            block = Block(
                self.frame, lambda: self._on_reset(activity), self._tl, self._theme_update
            )
            # Created after plugin_app(): EDMC must be asked to theme the whole block
            self._theme_update(block.frame)
            self._blocks[activity] = block
        return self._blocks[activity]

    def retranslate(self) -> None:
        """Refresh the texts that do not come from the model (language changed)."""
        for block in self._blocks.values():
            block.retranslate()

    def render(self, blocks: Sequence[ActivityBlock]) -> None:
        shown = {shown_block.activity for shown_block in blocks}
        for row, shown_block in enumerate(blocks):
            block = self.block(shown_block.activity)
            block.render(shown_block.model)
            block.frame.grid(row=row, column=0, sticky=tk.EW, pady=(BLOCK_GAP if row else 0, 0))
        for activity, block in self._blocks.items():
            if activity not in shown:
                block.frame.grid_remove()
