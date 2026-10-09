"""The window glue, with a stand-in for pywebview: no display needed."""

import json
import logging
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from edrockmaster.desktop import window as window_module
from edrockmaster.desktop.window import InterfaceApi, configure_logging, main


class FakeWindow:
    def __init__(self) -> None:
        self.scripts: list[str] = []

    def run_js(self, script: str) -> None:
        self.scripts.append(script)


class FakeGui:
    """Stands for the ``webview`` module: records the window, runs the page's first call."""

    def __init__(self) -> None:
        self.window = FakeWindow()
        self.created: dict[str, Any] = {}
        self.started: dict[str, Any] = {}

    def create_window(self, title: str, **options: Any) -> FakeWindow:
        self.created = {"title": title, **options}
        return self.window

    def start(self, **options: Any) -> None:
        self.started = options
        # The page loads and says it is ready; the core answers with the live view
        api: InterfaceApi = self.created["js_api"]
        api.ready()
        deadline = time.monotonic() + 5
        while not self.window.scripts and time.monotonic() < deadline:
            time.sleep(0.01)
        api.reset("mining")
        api.dismiss_notice()
        api.shown()
        assert api.catalogue()["modules"]
        api.add_goal({"kind": "effect", "module": "fsd", "name": "special_fsd_heavy"})
        api.change_goal("nowhere", 2)
        api.remove_goal("nowhere")
        settings = api.settings()
        api.save_settings(settings)


@pytest.fixture
def interface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    page = tmp_path / "interface" / "index.html"
    page.parent.mkdir()
    page.write_text("<!doctype html><title>EDRockMaster</title>", encoding="utf-8")
    monkeypatch.setattr(window_module, "INTERFACE", page)
    return page


def test_the_window_shows_the_interface_and_receives_the_live_view(
    tmp_path: Path, interface: Path
) -> None:
    gui = FakeGui()
    environ = {"EDROCKMASTER_JOURNAL_DIR": str(tmp_path / "journal")}
    assert main([], environ, gui, tmp_path / "data") == 0  # type: ignore[arg-type]
    assert gui.created["title"] == "EDRockMaster"
    assert gui.created["html"].startswith("<!doctype html>")
    assert gui.started == {"private_mode": True, "debug": False}
    script = gui.window.scripts[0]
    prefix = "window.edrm && window.edrm.receive("
    assert script.startswith(prefix)
    view = json.loads(script[len(prefix) : -1])
    assert view["journal"]["folder"] == str(tmp_path / "journal")


def test_the_demo_reads_a_sample_journal_and_keeps_the_player_s_data(
    tmp_path: Path, interface: Path, caplog: pytest.LogCaptureFixture
) -> None:
    gui = FakeGui()
    environ = {"EDROCKMASTER_JOURNAL_DIR": str(tmp_path / "journal")}
    data = tmp_path / "data"
    with caplog.at_level(logging.INFO):
        assert main(["--demo"], environ, gui, data) == 0  # type: ignore[arg-type]
    prefix = "window.edrm && window.edrm.receive("
    view = json.loads(gui.window.scripts[0][len(prefix) : -1])
    demo = Path(view["journal"]["folder"]).parent
    assert demo.name.startswith("edrockmaster-demo-")
    assert not demo.exists()  # deleted at exit
    # The settings saved during the demo were not the player's
    assert sorted(path.name for path in data.iterdir()) == ["logs"]
    assert "Demo mode (" in caplog.text


@pytest.mark.parametrize(
    ("argument", "language"), [("--demo=en", "en"), ("--demo=fr", "fr"), ("--demo=de", None)]
)
def test_the_demo_in_a_language(
    tmp_path: Path,
    interface: Path,
    monkeypatch: pytest.MonkeyPatch,
    argument: str,
    language: str | None,
) -> None:
    monkeypatch.setattr(window_module, "system_language", lambda: "fr")
    gui = FakeGui()
    assert main([argument], {}, gui, tmp_path / "data") == 0  # type: ignore[arg-type]
    prefix = "window.edrm && window.edrm.receive("
    view = json.loads(gui.window.scripts[0][len(prefix) : -1])
    assert view["language"] == (language or "fr")  # the system's when not one the application has
    assert "edrockmaster-demo-" in view["journal"]["folder"]


def test_debug_on_request(tmp_path: Path, interface: Path) -> None:
    gui = FakeGui()
    main(["--debug"], {}, gui, tmp_path / "data")  # type: ignore[arg-type]
    assert gui.started["debug"] is True


def test_an_interface_not_built_is_said(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(window_module, "INTERFACE", tmp_path / "missing.html")
    with caplog.at_level(logging.ERROR):
        assert main([], {}, SimpleNamespace(), tmp_path / "data") == 1  # type: ignore[arg-type]
    assert "pnpm build" in caplog.text


def test_logs_go_to_a_rotating_file(tmp_path: Path) -> None:
    logger = configure_logging(tmp_path)
    logger.info("hello")
    for handler in logger.handlers:
        handler.flush()
    assert "hello" in (tmp_path / "logs" / "edrockmaster.log").read_text(encoding="utf-8")
    assert configure_logging(tmp_path) is logger  # configured once


def test_no_log_file_where_the_folder_cannot_be(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(window_module, "LOGGER_NAME", "edrockmaster-test-no-file")
    blocked = tmp_path / "blocked"
    blocked.write_text("a file, not a folder")
    configure_logging(blocked)
    assert "no log file" in capsys.readouterr().err


@pytest.fixture(autouse=True)
def fresh_logger() -> Any:
    logger = logging.getLogger(window_module.LOGGER_NAME)
    saved = list(logger.handlers)
    logger.handlers.clear()
    yield
    for handler in logger.handlers:
        handler.close()
    logger.handlers[:] = saved


def test_a_view_before_the_window_exists_is_dropped() -> None:
    window_module._Window().push({"version": 1})  # no window yet: nothing to do


def test_no_console_logging_without_a_console(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stderr", None)
    logger = configure_logging(tmp_path)
    assert all(
        not isinstance(h, logging.StreamHandler) or isinstance(h, logging.FileHandler)
        for h in logger.handlers
    )


def test_no_log_file_and_no_console(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stderr", None)
    blocked = tmp_path / "blocked"
    blocked.write_text("a file, not a folder")
    assert configure_logging(blocked).handlers == []


def test_a_window_that_cannot_run_is_logged(
    tmp_path: Path, interface: Path, caplog: pytest.LogCaptureFixture
) -> None:
    gui = FakeGui()

    def broken(**_options: Any) -> None:
        raise OSError("WebView2 is not installed")

    gui.start = broken  # type: ignore[method-assign]
    told: list[str] = []
    with caplog.at_level(logging.ERROR):
        assert main([], {}, gui, tmp_path / "data", told.append) == 1  # type: ignore[arg-type]
    assert "WebView2 is not installed" in caplog.text
    [message] = told
    assert "could not open its window" in message


def test_the_player_is_told_why_the_window_failed(tmp_path: Path) -> None:
    log = tmp_path / "logs" / "edrockmaster.log"
    message = window_module.failure_message(OSError("WebView2 is not installed"), log)
    assert "WebView2 is not installed" in message
    assert str(log) in message
    assert "Unblock" not in message
    blocked = RuntimeError("Failed to resolve Python.Runtime.Loader.Initialize from U:\\x.dll")
    assert "Unblock" in window_module.failure_message(blocked, log)
