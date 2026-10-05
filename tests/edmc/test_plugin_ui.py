"""EDMC's UI hooks wired to the panel and the preferences tab (needs a display)."""

import logging
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path

import pytest

from edrockmaster.application.activity import Activity
from edrockmaster.application.settings import DisplayMode
from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.edmc.plugin import Plugin
from edrockmaster.ui.panel import Block
from tests.fakes import FakeConfig

PROSPECTED: Entry = {
    "timestamp": "2026-10-03T12:00:00Z",
    "event": "ProspectedAsteroid",
    "Materials": [{"Name": "Painite", "Proportion": 40.0}],
    "Content": "$AsteroidMaterialContent_High;",
    "Remaining": 100.0,
}


class Harness:
    def __init__(self, root: tk.Tk, tmp_path: Path) -> None:
        self.config = FakeConfig()
        self.opened: list[Path] = []
        self.plugin = Plugin(
            self.config, data_directory=lambda: tmp_path / "data", open_folder=self.opened.append
        )
        self.plugin.start(tmp_path)
        self.frame = self.plugin.app(root)

    def block(self, activity: Activity | None = None) -> Block:
        """The block of an activity; by default, the only one shown."""
        panel = self.plugin._panel
        assert panel is not None
        if activity is None:
            [activity] = [a for a in Activity if panel.block(a).frame.grid_info()]
        return panel.block(activity)

    def status(self, activity: Activity | None = None) -> str:
        return str(self.block(activity)._status["text"])


@pytest.fixture
def harness(root: tk.Tk, tmp_path: Path) -> Iterator[Harness]:
    harness = Harness(root, tmp_path)
    yield harness
    harness.plugin.stop()


def test_app_shows_the_panel_and_attaches_the_sound(harness: Harness) -> None:
    assert isinstance(harness.frame, tk.Frame)
    assert harness.status() == "No mining session"
    assert harness.plugin._play_alert is not None


def test_journal_entries_refresh_the_panel(harness: Harness) -> None:
    harness.plugin.journal_entry("Cmdr", False, None, None, PROSPECTED, {})
    assert harness.status() == "Mining"
    assert harness.block()._alert["text"] == "Painite 40.0 %"


def test_reset_button_ends_the_session(harness: Harness) -> None:
    harness.plugin.journal_entry("Cmdr", False, None, None, PROSPECTED, {})
    harness.block()._reset.invoke()
    assert harness.status() == "Session ended: reset"


def test_preferences_are_applied_and_saved_when_the_dialog_closes(
    harness: Harness, root: tk.Tk
) -> None:
    harness.plugin.prefs(root)
    tab = harness.plugin._tab
    assert tab is not None
    tab._thresholds["painite"].set("45")
    harness.plugin.prefs_changed()
    companion = harness.plugin.companion
    assert companion is not None
    assert companion.settings.alerts.thresholds[Commodity.from_symbol("painite")] == 45.0
    assert '"painite": 45.0' in str(harness.config.values["edrockmaster.alert.thresholds"])
    harness.plugin.journal_entry("Cmdr", False, None, None, PROSPECTED, {})
    assert not harness.block()._alert.grid_info()  # 40 % is now below the threshold


def test_invalid_entries_are_reported(
    harness: Harness, root: tk.Tk, caplog: pytest.LogCaptureFixture
) -> None:
    harness.plugin.prefs(root)
    assert harness.plugin._tab is not None
    harness.plugin._tab._thresholds["painite"].set("lots")
    with caplog.at_level(logging.WARNING):
        harness.plugin.prefs_changed()
    assert "Invalid entries ignored: Painite" in caplog.text


def test_closing_the_dialog_twice_is_harmless(harness: Harness, root: tk.Tk) -> None:
    harness.plugin.prefs(root)
    harness.plugin.prefs_changed()
    harness.plugin.prefs_changed()


def test_recordings_folder_is_created_and_opened(harness: Harness, root: tk.Tk) -> None:
    harness.plugin.open_recordings()
    [folder] = harness.opened
    assert folder.name == "recordings"
    assert folder.is_dir()


BOUNTY: Entry = {
    "timestamp": "2026-10-03T12:10:00Z",
    "event": "Bounty",
    "Rewards": [{"Faction": "Federation", "Reward": 250000}],
    "TotalReward": 250000,
    "Target": "anaconda",
}


def test_a_kill_switches_the_panel_to_combat(harness: Harness) -> None:
    harness.plugin.journal_entry("Cmdr", False, None, None, PROSPECTED, {})
    harness.plugin.journal_entry("Cmdr", False, None, None, BOUNTY, {})
    # A pirate shot down while mining: a miscellaneous kill, on no combat site
    assert harness.status() == "Combat"


def test_reset_acts_on_the_activity_shown(harness: Harness) -> None:
    harness.plugin.journal_entry("Cmdr", False, None, None, PROSPECTED, {})
    harness.plugin.journal_entry("Cmdr", False, None, None, BOUNTY, {})
    harness.block()._reset.invoke()
    assert harness.status() == "Combat session ended: reset"
    companion = harness.plugin.companion
    assert companion is not None
    assert companion.mining.current_stats is not None


def test_stacked_display_shows_both_activities_with_their_own_reset(
    harness: Harness, root: tk.Tk
) -> None:
    harness.plugin.prefs(root)
    tab = harness.plugin._tab
    assert tab is not None
    tab._display_mode.set(DisplayMode.STACKED.value)
    harness.plugin.prefs_changed()
    assert harness.config.values["edrockmaster.display.mode"] == "stacked"
    harness.plugin.journal_entry("Cmdr", False, None, None, PROSPECTED, {})
    harness.plugin.journal_entry("Cmdr", False, None, None, BOUNTY, {})
    assert harness.status(Activity.MINING) == "Mining"
    assert harness.status(Activity.COMBAT) == "Combat"
    harness.block(Activity.MINING)._reset.invoke()
    assert harness.status(Activity.MINING) == "Session ended: reset"
    assert harness.status(Activity.COMBAT) == "Combat"


def test_hiding_an_activity_hides_its_block(harness: Harness, root: tk.Tk) -> None:
    harness.plugin.prefs(root)
    tab = harness.plugin._tab
    assert tab is not None
    tab._activities[Activity.MINING].set(False)
    harness.plugin.prefs_changed()
    harness.plugin.journal_entry("Cmdr", False, None, None, PROSPECTED, {})
    assert harness.status() == "No combat session"
