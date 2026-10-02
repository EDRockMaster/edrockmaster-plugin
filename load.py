"""EDMC entry points of the EDRockMaster plugin.

EDMC imports this module and calls the hooks below. They only delegate to
``edrockmaster.edmc.plugin``; nothing else belongs here.
"""

from __future__ import annotations

from typing import Any

from edrockmaster import VERSION
from edrockmaster.edmc.plugin import Plugin

__all__ = ["VERSION", "journal_entry", "plugin_start3", "plugin_stop"]

_plugin = Plugin()


def plugin_start3(plugin_dir: str) -> str:
    return _plugin.start(plugin_dir)


def plugin_stop() -> None:
    _plugin.stop()


def journal_entry(
    cmdr: str,
    is_beta: bool,
    system: str | None,
    station: str | None,
    entry: dict[str, Any],
    state: dict[str, Any],
) -> str | None:
    return _plugin.journal_entry(cmdr, is_beta, system, station, entry, state)
