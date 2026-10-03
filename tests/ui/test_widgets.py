"""Widget tests: real tkinter, skipped where no display is available (e.g. CI)."""

import tkinter as tk

from edrockmaster.application.settings import DEFAULT_SETTINGS
from edrockmaster.domain.mining.journal import ContentLevel
from edrockmaster.ui.panel import Panel
from edrockmaster.ui.panel_model import PanelModel, StatLine
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
    resets: list[None] = []
    themed: list[tk.Widget] = []
    panel = Panel(root, lambda: resets.append(None), identity, themed.append)
    panel.render(MODEL)
    assert panel._status["text"] == MODEL.status
    assert panel._alert["text"] == "Painite 41.0 %"
    assert shown(panel._alert)
    assert [(label["text"], value["text"]) for label, value in panel._rows] == [
        ("Refined", "12 t"),
        ("Rate", "30.0 t/h"),
    ]
    assert len(themed) == 4  # rows created after plugin_app() are themed
    panel._reset.invoke()
    assert resets == [None]


def test_panel_hides_what_the_model_no_longer_has(root: tk.Tk) -> None:
    panel = Panel(root, lambda: None, identity)
    panel.render(MODEL)
    panel.render(PanelModel(status="No mining session", lines=(), alert=None, can_reset=False))
    assert not shown(panel._alert)
    assert not any(shown(label) for label, _ in panel._rows)
    assert str(panel._reset["state"]) == tk.DISABLED


def test_panel_retranslates_its_own_texts(root: tk.Tk) -> None:
    language = {"prefix": ""}
    panel = Panel(root, lambda: None, lambda text: language["prefix"] + text)
    language["prefix"] = "fr:"
    panel.retranslate()
    assert panel._reset["text"] == "fr:Reset"


def test_preferences_tab_gives_back_what_it_shows(root: tk.Tk) -> None:
    values = values_from_settings(DEFAULT_SETTINGS, fmt)
    rows = threshold_rows(DEFAULT_SETTINGS, identity)
    tab = PreferencesTab(root, values, rows, identity, lambda: None)
    assert tab.values() == values


def test_preferences_tab_reads_the_edited_fields(root: tk.Tk) -> None:
    values = values_from_settings(DEFAULT_SETTINGS, fmt)
    tab = PreferencesTab(
        root, values, threshold_rows(DEFAULT_SETTINGS, identity), identity, lambda: None
    )
    tab._thresholds["painite"].set("40")
    tab._content.set("High")
    tab._remaining.set("50")
    tab._sound.set(False)
    tab._record.set(True)
    edited = tab.values()
    assert edited.thresholds["painite"] == "40"
    assert edited.minimum_content is ContentLevel.HIGH
    assert edited.minimum_remaining == "50"
    assert not edited.sound_enabled
    assert edited.record_journal
