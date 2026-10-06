"""Widget tests: real tkinter, skipped where no display is available (e.g. CI)."""

import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

import pytest

from edrockmaster.application.activity import Activity
from edrockmaster.application.settings import DEFAULT_SETTINGS, DisplayMode
from edrockmaster.domain.mining.journal import ContentLevel
from edrockmaster.ui import preferences
from edrockmaster.ui.panel import Panel
from edrockmaster.ui.panel_model import ActivityBlock, PanelModel, StatLine
from edrockmaster.ui.preferences import PreferencesTab
from edrockmaster.ui.preferences_form import threshold_rows, values_from_settings


def fmt(number: float, decimals: int) -> str:
    return f"{number:.{decimals}f}"


def identity(text: str) -> str:
    return text


def shown(widget: tk.Widget) -> bool:
    return bool(widget.grid_info())


MODEL = PanelModel(
    status="Mining: Col 285 2 A Ring",
    lines=(StatLine("Refined", "12 t"), StatLine("Rate", "30.0 t/h")),
    alert="Painite 41.0 %",
    can_reset=True,
)


def test_panel_copies_the_model(root: tk.Tk) -> None:
    resets: list[Activity] = []
    themed: list[tk.Widget] = []
    panel = Panel(root, resets.append, identity, themed.append)
    panel.render((ActivityBlock(Activity.MINING, MODEL),))
    block = panel.block(Activity.MINING)
    assert block._status["text"] == MODEL.status
    assert block._alert["text"] == "Painite 41.0 %"
    assert shown(block._alert)
    assert [(label["text"], value["text"]) for label, value in block._rows] == [
        ("Refined", "12 t"),
        ("Rate", "30.0 t/h"),
    ]
    # Created after plugin_app(), the block and its rows are themed
    assert themed == [block.frame] + [widget for row in block._rows for widget in row]
    block._reset.invoke()
    assert resets == [Activity.MINING]


def test_panel_hides_what_the_model_no_longer_has(root: tk.Tk) -> None:
    panel = Panel(root, lambda _: None, identity)
    panel.render((ActivityBlock(Activity.MINING, MODEL),))
    empty = PanelModel(status="No mining session", lines=(), alert=None, can_reset=False)
    panel.render((ActivityBlock(Activity.MINING, empty),))
    block = panel.block(Activity.MINING)
    assert not shown(block._alert)
    assert not any(shown(label) for label, _ in block._rows)
    assert str(block._reset["state"]) == tk.DISABLED


def test_panel_stacks_one_block_per_activity_in_order(root: tk.Tk) -> None:
    resets: list[Activity] = []
    panel = Panel(root, resets.append, identity)
    combat = PanelModel(status="Combat", lines=(), alert=None, can_reset=True)
    panel.render((ActivityBlock(Activity.MINING, MODEL), ActivityBlock(Activity.COMBAT, combat)))
    mining_block, combat_block = panel.block(Activity.MINING), panel.block(Activity.COMBAT)
    assert shown(mining_block.frame)
    assert shown(combat_block.frame)
    assert mining_block.frame.grid_info()["row"] < combat_block.frame.grid_info()["row"]
    combat_block._reset.invoke()
    assert resets == [Activity.COMBAT]
    panel.render((ActivityBlock(Activity.COMBAT, combat),))
    assert not shown(mining_block.frame)
    assert shown(combat_block.frame)


def test_panel_retranslates_its_own_texts(root: tk.Tk) -> None:
    language = {"prefix": ""}
    panel = Panel(root, lambda _: None, lambda text: language["prefix"] + text)
    panel.render((ActivityBlock(Activity.COMBAT, MODEL),))
    language["prefix"] = "fr:"
    panel.retranslate()
    assert panel.block(Activity.COMBAT)._reset["text"] == "fr:Reset"


def test_preferences_tab_gives_back_what_it_shows(root: tk.Tk) -> None:
    values = values_from_settings(DEFAULT_SETTINGS, fmt)
    rows = threshold_rows(DEFAULT_SETTINGS, identity)
    tab = PreferencesTab(root, values, rows, identity, lambda: None, build_version="0.3.0-dev")
    assert tab.values() == values


def test_preferences_tab_reads_the_edited_fields(root: tk.Tk) -> None:
    values = values_from_settings(DEFAULT_SETTINGS, fmt)
    tab = PreferencesTab(
        root,
        values,
        threshold_rows(DEFAULT_SETTINGS, identity),
        identity,
        lambda: None,
        build_version="0.3.0-dev",
    )
    tab._thresholds["painite"].set("40")
    tab._content.set("High")
    tab._remaining.set("50")
    tab._sound.set(False)
    tab._record.set(True)
    tab._activities[Activity.MINING].set(False)
    tab._display_mode.set(DisplayMode.STACKED.value)
    edited = tab.values()
    assert edited.thresholds["painite"] == "40"
    assert edited.minimum_content is ContentLevel.HIGH
    assert edited.minimum_remaining == "50"
    assert not edited.sound_enabled
    assert edited.record_journal
    assert edited.activities == {Activity.MINING: False, Activity.COMBAT: True}
    assert edited.display_mode is DisplayMode.STACKED


class EdmcFrame(ttk.Frame):
    """Like EDMC's ``myNotebook.Frame``: it grids a top spacer in itself."""

    def __init__(self, master: tk.Misc | None = None, **kw: object) -> None:
        super().__init__(master, **kw)  # type: ignore[arg-type]
        ttk.Frame(self).grid(pady=5)


def test_preferences_tab_builds_with_edmc_frames(
    root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression: in EDMC 0.3.0-rc.2 the tab failed, "pack" inside a frame managed by grid
    edmc_notebook = SimpleNamespace(**{name: getattr(ttk, name) for name in dir(ttk)})
    edmc_notebook.Frame = EdmcFrame
    monkeypatch.setattr(preferences, "nb", edmc_notebook)
    values = values_from_settings(DEFAULT_SETTINGS, fmt)
    tab = PreferencesTab(
        root, values, threshold_rows(DEFAULT_SETTINGS, identity), identity, lambda: None
    )
    assert tab.values() == values
