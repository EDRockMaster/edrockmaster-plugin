"""Wiring between EDMC's hooks and the plugin's application layer."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

from edrockmaster.domain.journal import parse_entry

try:  # pragma: no cover - only available inside EDMC
    from config import appname  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - outside EDMC (tests, tooling)
    appname = "EDMarketConnector"

PLUGIN_NAME = "EDRockMaster"

logger = logging.getLogger(
    f"{appname}.{os.path.basename(os.path.dirname(os.path.dirname(__file__)))}"
)


class Plugin:
    """The plugin as seen by EDMC."""

    def start(self, plugin_dir: str) -> str:
        logger.info("EDRockMaster started from %s", plugin_dir)
        return PLUGIN_NAME

    def stop(self) -> None:
        logger.info("EDRockMaster stopped")

    def journal_entry(
        self,
        cmdr: str,
        is_beta: bool,
        system: str | None,
        station: str | None,
        entry: Mapping[str, Any],
        state: Mapping[str, Any],
    ) -> str | None:
        fact = parse_entry(entry)
        if fact is not None:
            logger.debug("Journal fact: %s", fact)
        return None
