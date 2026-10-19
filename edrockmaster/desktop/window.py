"""The window of the desktop application (ADR 0020, ADR 0021), and its entry point.

pywebview shows the interface, one self-contained HTML file built from ``web/``,
given as a page: no server, no port. The interface calls the core through
``InterfaceApi`` (``window.pywebview.api``); the core pushes the live view with
``run_js``, which does not wait for the page. pywebview owns the main thread
until the window closes; the core then stops.

Run it with ``python -m edrockmaster.desktop``; ``--demo`` reads a sample journal
instead of the player's (``demo.py``), in the system's language or the one it
names (``--demo=en``, ``--demo=fr``); ``--debug`` opens the web inspector.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import webview

from edrockmaster.desktop.core import DesktopCore, Push
from edrockmaster.desktop.demo import write_demo_journal
from edrockmaster.desktop.folder_opener import open_in_file_manager
from edrockmaster.desktop.journal_folder import environment_override
from edrockmaster.desktop.phone import Phone, remote_calls
from edrockmaster.desktop.settings_view import LANGUAGES
from edrockmaster.infrastructure.paths import data_directory
from edrockmaster.infrastructure.strings_catalogue import system_language

INTERFACE = Path(__file__).with_name("interface") / "index.html"
TITLE = "EDRockMaster"
LOGGER_NAME = "edrockmaster"
LOG_FILE_BYTES = 1_000_000
LOG_FILES_KEPT = 3
DEMO = "--demo"
WINDOW = {"width": 1100, "height": 760, "min_size": (520, 400), "background_color": "#0d0f12"}
WINDOW_ONLY = frozenset({"open_folder", "restart_to_update"})
"""Calls that act on the computer itself: a phone or a tablet does not make them (ADR 0055)."""


class InterfaceApi:
    """What the interface may call. Each call only queues work for the core thread; the calls
    of a context go to its handler (ADR 0041)."""

    def __init__(self, core: DesktopCore, window: _Window) -> None:
        self._core = core
        self._window = window

    def ready(self) -> None:
        self._core.ready()

    def reset(self, activity: str) -> None:
        self._core.reset(activity)

    def dismiss_notice(self) -> None:
        self._core.dismiss_notice()

    def restart_to_update(self) -> None:
        """The window closes; the version ready is applied, then the application starts again
        (ADR 0053)."""
        if self._core.restart_to_update():
            self._window.close()

    def shown(self) -> None:
        self._core.shown()

    def catalogue(self) -> dict[str, Any]:
        """Returned to the page: the goal form's choices, read once."""
        return self._core.handlers.engineering.catalogue()

    def add_goal(self, request: dict[str, Any]) -> None:
        self._core.handlers.engineering.add_goal(request)

    def change_goal(self, goal_id: str, count: int) -> None:
        self._core.handlers.engineering.change_goal(goal_id, count)

    def remove_goal(self, goal_id: str) -> None:
        self._core.handlers.engineering.remove_goal(goal_id)

    def order_goals(self, order: list[str]) -> None:
        """The player's priority (ADR 0033): goal ids, first to last."""
        self._core.handlers.engineering.order_goals(order)

    def settings(self) -> dict[str, Any]:
        """Returned to the page: what the settings form shows."""
        return self._core.handlers.settings.settings()

    def save_settings(self, request: dict[str, Any]) -> None:
        self._core.handlers.settings.save_settings(request)

    def open_folder(self, name: str) -> None:
        """``recordings`` or ``logs``: any other name is refused by the handler."""
        self._core.handlers.settings.open_folder(name)

    def read_past_journals(self) -> None:
        """Forget what the journals of past game sessions gave, and read them all again."""
        self._core.handlers.settings.read_past_journals()

    def layout(self) -> dict[str, Any]:
        """Returned to the page: the order of the cards of each view, and those folded."""
        return self._core.handlers.layout.layout()

    def save_layout(self, view: str, layout: dict[str, Any]) -> None:
        self._core.handlers.layout.save_layout(view, layout)

    # The Mining tab (ADR 0040): pywebview runs each call on a thread of its own, so these may
    # wait for the community sources; the page gets their answer as the call's result

    def mining_options(self) -> dict[str, Any]:
        return self._core.handlers.mining.mining_options()

    def find_hotspots(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._core.handlers.mining.find_hotspots(request)

    def find_buyers(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._core.handlers.mining.find_buyers(request)

    def estimate_cargo(self) -> dict[str, Any]:
        return self._core.handlers.mining.estimate_cargo()

    # The phone and tablet (ADR 0055): answered at once, the local server started or stopped

    def phone(self) -> dict[str, Any]:
        return self._core.handlers.phone.phone()

    def set_phone(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._core.handlers.phone.set_phone(request)

    def new_phone_link(self) -> dict[str, Any]:
        return self._core.handlers.phone.new_phone_link()

    def use_phone_address(self, address: str) -> dict[str, Any]:
        return self._core.handlers.phone.use_phone_address(address)


REMOTE_CALLS = remote_calls(InterfaceApi, WINDOW_ONLY)


def remote_call(api: InterfaceApi, name: str, arguments: list[Any]) -> Any:
    """A call of a phone or a tablet; ``KeyError`` for one it may not make."""
    if name not in REMOTE_CALLS:
        raise KeyError(name)
    return getattr(api, name)(*arguments)


class _Window:
    """The pywebview window, known once created: the core's pushes go to it."""

    def __init__(self) -> None:
        self.window: Any = None

    def push(self, view: Mapping[str, Any]) -> None:
        if self.window is not None:
            # ASCII only: pywebview on GTK gives WebKit the script's length in characters, not bytes
            payload = json.dumps(view, ensure_ascii=True)
            self.window.run_js(f"window.edrm && window.edrm.receive({payload})")

    def close(self) -> None:
        if self.window is not None:
            self.window.destroy()


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
    alert: Callable[[str], None] | None = None,
) -> int:
    """Run the application; ``alert`` tells the player of a failure (a message box)."""
    directory = data if data is not None else data_directory()
    logger = configure_logging(directory)
    if not INTERFACE.is_file():
        logger.error("The interface is not built: run 'pnpm build' in web/ (%s missing)", INTERFACE)
        return 1
    with ExitStack() as demo:
        # The usual folder and the one the settings name are the core's to find
        folder = environment_override(environ)
        core_data = directory
        language = system_language()
        demo_language = _demo_language(argv)
        if demo_language is not None:
            language = demo_language or language
            folder, core_data = _demo(demo, language, logger)
        window = _Window()
        push: Push = window.push

        def call(name: str, arguments: list[Any]) -> Any:
            return remote_call(api, name, arguments)

        phone = Phone(call, lambda: INTERFACE.read_text(encoding="utf-8"), logger)
        core = DesktopCore(
            data_directory=core_data,
            journal_folder=folder,
            push=push,
            language=language,
            logger=logger,
            logs_directory=directory / "logs",
            open_folder=open_in_file_manager,
            phone=phone,
        )
        api = InterfaceApi(core, window)
        window.window = gui.create_window(
            # The title bar carries the full version (ADR 0016): the page does not repeat it
            f"{TITLE} {core.build.version}",
            html=INTERFACE.read_text(encoding="utf-8"),
            js_api=api,
            **WINDOW,
        )
        core.start()
        try:
            gui.start(private_mode=True, debug="--debug" in argv)
        except Exception as error:
            # No console in the packaged application: the log and a message box say it
            logger.exception("The window could not run")
            (alert or show_error)(failure_message(error, directory / "logs" / "edrockmaster.log"))
            return 1
        finally:
            core.stop()
    return 0


def _demo_language(argv: Sequence[str]) -> str | None:
    """``None``: no demo; ``""``: the demo, in the system's language; else its language."""
    for argument in argv:
        if argument == DEMO:
            return ""
        if argument.startswith(f"{DEMO}="):
            chosen = argument.partition("=")[2]
            return chosen if chosen in LANGUAGES[1:] else ""
    return None


def _demo(stack: ExitStack, language: str, logger: logging.Logger) -> tuple[Path, Path]:
    """The demo's journal folder and data directory, in a folder deleted at exit."""
    temporary = Path(
        stack.enter_context(
            tempfile.TemporaryDirectory(prefix="edrockmaster-demo-", ignore_cleanup_errors=True)
        )
    )
    write_demo_journal(temporary / "journal", datetime.now(UTC), language)
    logger.info("Demo mode (%s): a sample journal, settings and goals in %s", language, temporary)
    return temporary / "journal", temporary / "data"


_BLOCKED_HINT = (
    "Windows may have blocked the application's files because they were downloaded. "
    "Right-click the downloaded zip, Properties, tick Unblock, then extract it again "
    "on a local disk."
)


def failure_message(error: BaseException, log: Path) -> str:
    """What the player is told when the window cannot open, in English: the language
    catalogues live in the window that failed."""
    text = f"EDRockMaster could not open its window.\n\n{error}"
    # .NET refuses to load a library marked as downloaded (Mark of the Web)
    if "Python.Runtime" in str(error):
        text += f"\n\n{_BLOCKED_HINT}"
    return f"{text}\n\nDetails in {log}"


def show_error(message: str, platform: str = sys.platform) -> None:  # pragma: no cover - Windows
    """A message box on Windows, where the packaged application has no console."""
    if platform != "win32":
        return
    import ctypes  # noqa: PLC0415 - Windows only

    error_icon = 0x10
    ctypes.windll.user32.MessageBoxW(None, message, TITLE, error_icon)  # type: ignore[attr-defined]
