"""The plugin's panel in EDMC's main window (tkinter, main thread only).

It only copies the texts of a ``PanelModel``: every decision is the presenter's.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from edrockmaster.ui.presenter import PanelModel

ALERT_COLOUR = "#ff8c00"


def _no_theme(_widget: tk.Widget) -> None:
    pass


class Panel:
    def __init__(
        self,
        parent: tk.Misc,
        on_reset: Callable[[], None],
        translate: Callable[[str], str],
        theme_update: Callable[[tk.Widget], None] = _no_theme,
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
        """Refresh the texts that do not come from the model (language changed)."""
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
