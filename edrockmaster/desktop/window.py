"""The window of the desktop application (ADR 0020, ADR 0021), and its entry point.

pywebview shows the interface, one self-contained HTML file built from ``web/``,
given as a page: no server, no port. The interface calls the core through
``InterfaceApi`` (``window.pywebview.api``); the core pushes the live view with
``run_js``, which does not wait for the page. pywebview owns the main thread
until the window closes; the core then stops.

Run it with ``python -m edrockmaster.desktop``.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import webview

from edrockmaster.desktop.core import DesktopCore, Push
from edrockmaster.desktop.journal_folder import default_journal_folder, environment_override
from edrockmaster.infrastructure.paths import data_directory
from edrockmaster.infrastructure.strings_catalogue import system_language

INTERFACE = Path(__file__).with_name("interface") / "index.html"
TITLE = "EDRockMaster"
LOGGER_NAME = "edrockmaster"
LOG_FILE_BYTES = 1_000_000
LOG_FILES_KEPT = 3
WINDOW = {"width": 1100, "height": 760, "min_size": (520, 400), "background_color": "#0d0f12"}


class InterfaceApi:
    """What the interface may call. Each call only queues work for the core thread."""

    def __init__(self, core: DesktopCore) -> None:
        self._core = core

    def ready(self) -> None:
        self._core.ready()

    def reset(self, activity: str) -> None:
        self._core.reset(activity)

    def dismiss_notice(self) -> None:
        self._core.dismiss_notice()


class _Window:
    """The pywebview window, known once created: the core's pushes go to it."""

    def __init__(self) -> None:
        self.window: Any = None

    def push(self, view: Mapping[str, Any]) -> None:
        if self.window is not None:
            # ASCII only: pywebview on GTK gives WebKit the script's length in characters, not bytes
            payload = json.dumps(view, ensure_ascii=True)
            self.window.run_js(f"window.edrm && window.edrm.receive({payload})")


def configure_logging(directory: Path) -> logging.Logger:
    """A rotating log file in the data directory, and the standard error."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s")
    try:
        (directory / "logs").mkdir(parents=True, exist_ok=True)
        to_file = logging.handlers.RotatingFileHandler(
            directory / "logs" / "edrockmaster.log",
            maxBytes=LOG_FILE_BYTES,
            backupCount=LOG_FILES_KEPT,
            encoding="utf-8",
        )
        to_file.setFormatter(formatter)
        logger.addHandler(to_file)
    except OSError as error:
        if sys.stderr is not None:
            print(f"EDRockMaster: no log file in {directory}: {error}", file=sys.stderr)
    # The packaged application has no console: no standard error to write to
    if sys.stderr is not None:
        to_console = logging.StreamHandler()
        to_console.setFormatter(formatter)
        logger.addHandler(to_console)
    return logger


def main(
    argv: Sequence[str] = (),
    environ: Mapping[str, str] = os.environ,
    gui: ModuleType = webview,
    data: Path | None = None,
) -> int:
    directory = data if data is not None else data_directory()
    logger = configure_logging(directory)
    if not INTERFACE.is_file():
        logger.error("The interface is not built: run 'pnpm build' in web/ (%s missing)", INTERFACE)
        return 1
    folder = environment_override(environ) or default_journal_folder()
    window = _Window()
    push: Push = window.push
    core = DesktopCore(
        data_directory=directory,
        journal_folder=folder,
        push=push,
        language=system_language(),
        logger=logger,
    )
    window.window = gui.create_window(
        TITLE, html=INTERFACE.read_text(encoding="utf-8"), js_api=InterfaceApi(core), **WINDOW
    )
    core.start()
    try:
        gui.start(private_mode=True, debug="--debug" in argv)
    finally:
        core.stop()
    return 0
