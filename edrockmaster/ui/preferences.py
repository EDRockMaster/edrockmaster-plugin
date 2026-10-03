"""The plugin's tab in EDMC's settings dialog (tkinter, main thread only)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from edrockmaster.domain.journal import ContentLevel
from edrockmaster.ui.preferences_form import PreferencesValues

try:  # pragma: no cover - only available inside EDMC
    import myNotebook as nb  # type: ignore[import-not-found]  # noqa: N813 - EDMC idiom
except ImportError:  # pragma: no cover - outside EDMC: plain ttk widgets
    nb = ttk

THRESHOLD_COLUMNS = 3
_CONTENT_LEVELS = {
    ContentLevel.LOW: "Low",
    ContentLevel.MEDIUM: "Medium",
    ContentLevel.HIGH: "High",
}
PAD = 10


class PreferencesTab:
    def __init__(
        self,
        parent: tk.Misc,
        values: PreferencesValues,
        rows: list[tuple[str, str]],
        translate: Callable[[str], str],
        open_recordings: Callable[[], None],
    ) -> None:
        tl = self._tl = translate
        self.frame: Any = nb.Frame(parent)
        self._sound = tk.BooleanVar(value=values.sound_enabled)
        self._cores = tk.BooleanVar(value=values.alert_on_cores)
        self._record = tk.BooleanVar(value=values.record_journal)
        self._remaining = tk.StringVar(value=values.minimum_remaining)
        self._content_names = {level: tl(name) for level, name in _CONTENT_LEVELS.items()}
        self._content = tk.StringVar(value=self._content_names[values.minimum_content])
        self._thresholds = {
            key: tk.StringVar(value=values.thresholds.get(key, "")) for key, _ in rows
        }

        row = 0
        nb.Label(self.frame, text=tl("Prospector alerts")).grid(
            row=row,
            column=0,
            columnspan=2 * THRESHOLD_COLUMNS,
            sticky=tk.W,
            padx=PAD,
            pady=(PAD, 0),
        )
        row += 1
        nb.Label(
            self.frame,
            text=tl(
                "Alert when an asteroid holds at least this percentage. Leave empty for no alert."
            ),
        ).grid(row=row, column=0, columnspan=2 * THRESHOLD_COLUMNS, sticky=tk.W, padx=PAD)
        row += 1
        for index, (key, name) in enumerate(rows):
            grid_row, column = row + index // THRESHOLD_COLUMNS, 2 * (index % THRESHOLD_COLUMNS)
            nb.Label(self.frame, text=name).grid(
                row=grid_row, column=column, sticky=tk.W, padx=(PAD, 2)
            )
            _entry(self.frame, self._thresholds[key]).grid(
                row=grid_row, column=column + 1, sticky=tk.W, padx=(0, PAD)
            )
        row += -(-len(rows) // THRESHOLD_COLUMNS)

        nb.Label(self.frame, text=tl("Minimum content")).grid(
            row=row, column=0, sticky=tk.W, padx=(PAD, 2), pady=(PAD, 0)
        )
        names = list(self._content_names.values())
        nb.OptionMenu(self.frame, self._content, self._content.get(), *names).grid(
            row=row, column=1, sticky=tk.W, pady=(PAD, 0)
        )
        nb.Label(self.frame, text=tl("Minimum remaining")).grid(
            row=row, column=2, sticky=tk.W, padx=(PAD, 2), pady=(PAD, 0)
        )
        _entry(self.frame, self._remaining).grid(row=row, column=3, sticky=tk.W, pady=(PAD, 0))
        row += 1
        for variable, text in (
            (self._cores, tl("Alert on cores (motherlodes)")),
            (self._sound, tl("Play a sound on alerts")),
        ):
            nb.Checkbutton(self.frame, text=text, variable=variable).grid(
                row=row, column=0, columnspan=2 * THRESHOLD_COLUMNS, sticky=tk.W, padx=PAD
            )
            row += 1

        nb.Label(self.frame, text=tl("Debugging")).grid(
            row=row,
            column=0,
            columnspan=2 * THRESHOLD_COLUMNS,
            sticky=tk.W,
            padx=PAD,
            pady=(PAD, 0),
        )
        row += 1
        nb.Checkbutton(
            self.frame, text=tl("Record the journal (for bug reports)"), variable=self._record
        ).grid(row=row, column=0, columnspan=4, sticky=tk.W, padx=PAD)
        nb.Button(self.frame, text=tl("Open recordings folder"), command=open_recordings).grid(
            row=row, column=4, columnspan=2, sticky=tk.E, padx=PAD
        )

    def values(self) -> PreferencesValues:
        levels = {name: level for level, name in self._content_names.items()}
        return PreferencesValues(
            thresholds={key: variable.get() for key, variable in self._thresholds.items()},
            minimum_content=levels.get(self._content.get(), ContentLevel.LOW),
            minimum_remaining=self._remaining.get(),
            alert_on_cores=self._cores.get(),
            sound_enabled=self._sound.get(),
            record_journal=self._record.get(),
        )


def _entry(parent: Any, variable: tk.StringVar) -> Any:
    entry_class = getattr(nb, "EntryMenu", ttk.Entry)
    return entry_class(parent, textvariable=variable, width=6)
