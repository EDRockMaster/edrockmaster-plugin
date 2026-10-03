"""EDMC entry points of the EDRockMaster plugin.

EDMC imports this module and calls the hooks below. They only delegate to
``edrockmaster.edmc.plugin``; nothing else belongs here.
"""

from __future__ import annotations

import os
import tkinter as tk
from typing import Any

from config import config  # type: ignore[import-not-found]  # EDMC's settings store

from edrockmaster import VERSION
from edrockmaster.edmc.plugin import Plugin

__all__ = [
    "VERSION",
    "journal_entry",
    "plugin_app",
    "plugin_prefs",
    "plugin_start3",
    "plugin_stop",
    "prefs_changed",
]

_plugin = Plugin(config)


def plugin_start3(plugin_dir: str | os.PathLike[str]) -> str:
    return _plugin.start(plugin_dir)


def plugin_stop() -> None:
    _plugin.stop()


def plugin_app(parent: tk.Frame) -> tk.Frame:
    return _plugin.app(parent)


def plugin_prefs(parent: Any, cmdr: str, is_beta: bool) -> tk.Widget:
    return _plugin.prefs(parent)


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    _plugin.prefs_changed()


def journal_entry(
    cmdr: str,
    is_beta: bool,
    system: str | None,
    station: str | None,
    entry: dict[str, Any],
    state: dict[str, Any],
) -> str | None:
    return _plugin.journal_entry(cmdr, is_beta, system, station, entry, state)
