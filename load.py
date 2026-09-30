"""Points d'entrée EDMC. La logique vit dans le paquet ``mining``."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Any

from config import appname  # type: ignore[import-not-found]

from mining.session import MiningSession

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f"{appname}.{plugin_name}")

session = MiningSession()


def plugin_start3(plugin_dir: str) -> str:
    logger.info("EDRockMaster loaded from %s", plugin_dir)
    return "EDRockMaster"


def plugin_stop() -> None:
    pass


def plugin_app(parent: tk.Frame) -> tk.Frame:
    frame = tk.Frame(parent)
    tk.Label(frame, text="EDRockMaster").grid(row=0, column=0, sticky=tk.W)
    return frame


def journal_entry(
    cmdr: str,
    is_beta: bool,
    system: str,
    station: str,
    entry: dict[str, Any],
    state: dict[str, Any],
) -> None:
    session.handle(entry)
