"""The desktop application's core, with real threads, a real journal file and a real database."""

import json
import logging
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from edrockmaster.application.activity import Activity
from edrockmaster.desktop.core import CORE_THREAD, DesktopCore
from edrockmaster.desktop.live_view import SCHEMA
from tests.desktop.test_parity import write_journal
from tests.test_replay import Replay

logger = logging.getLogger("test.desktop_core")
VALIDATOR = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
TRADE = "amano-verne-trade-2026-10-04.jsonl"


class Views:
    def __init__(self) -> None:
        self.received: list[dict[str, Any]] = []
        self.threads: set[str] = set()
        self._lock = threading.Lock()

    def push(self, view: dict[str, Any]) -> None:
        VALIDATOR.validate(view)
        with self._lock:
            self.received.append(view)
            self.threads.add(threading.current_thread().name)

    def wait_for(self, condition: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with self._lock:
                found: dict[str, Any] | None = next(
                    (view for view in reversed(self.received) if condition(view)), None
                )
            if found is not None:
                return found
            time.sleep(0.01)
        raise AssertionError(f"no such view among {len(self.received)}")


class Desktop:
    def __init__(self, tmp_path: Path, journal: Path | None, language: str = "en") -> None:
        self.data = tmp_path / "data"
        self.views = Views()
        self.core = DesktopCore(
            data_directory=self.data,
            journal_folder=journal,
            push=self.views.push,
            language=language,
            logger=logger,
            poll_interval=0.01,
        )


@pytest.fixture
def journal(tmp_path: Path) -> Path:
    folder = tmp_path / "journal"
    folder.mkdir()
    return folder


@pytest.fixture
def desktop(tmp_path: Path, journal: Path) -> Iterator[Desktop]:
    started = Desktop(tmp_path, journal)
    started.core.start()
    yield started
    started.core.stop()


def blocks(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {block["activity"]: block for block in view["activities"]}


def test_the_journal_read_gives_the_plugin_s_figures(desktop: Desktop, journal: Path) -> None:
    desktop.core.ready()
    write_journal(journal, TRADE, chunk=10_000)
    [expected] = Replay(TRADE).presenter.blocks_of((Activity.TRADE,))
    wanted = [(line.label, line.value) for line in expected.model.lines]

    def trade_as_the_plugin(view: dict[str, Any]) -> bool:
        lines = blocks(view)["trade"]["lines"]
        return [(line["label"], line["value"]) for line in lines] == wanted

    final = desktop.views.wait_for(trade_as_the_plugin)
    assert blocks(final)["trade"]["status"] == expected.model.status
    assert final["current"] == "trade"
    assert final["language"] == "en"
    assert final["journal"] == {"folder": str(journal), "file": "Journal.2026-10-08T014139.01.log"}
    # Every view is sent from the core thread only
    assert desktop.views.threads == {CORE_THREAD}


def test_the_interface_gets_the_current_view_when_ready(tmp_path: Path) -> None:
    desktop = Desktop(tmp_path, None)
    desktop.core.start()
    try:
        desktop.core.ready()
        view = desktop.views.wait_for(lambda v: True)
    finally:
        desktop.core.stop()
    assert view["journal"] == {"folder": None, "file": None}
    assert [block["activity"] for block in view["activities"]] == [a.value for a in Activity]
    assert view["notice"] is None


def test_reset_ends_the_session_of_an_activity(desktop: Desktop, journal: Path) -> None:
    desktop.core.ready()
    write_journal(journal, TRADE, chunk=10_000)
    desktop.views.wait_for(lambda v: blocks(v)["trade"]["canReset"] or v["current"] == "trade")
    desktop.core.reset("trade")
    view = desktop.views.wait_for(lambda v: "reset" in blocks(v)["trade"]["status"])
    assert not blocks(view)["trade"]["canReset"]


def test_a_reset_of_an_unknown_activity_is_logged(
    desktop: Desktop, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        desktop.core.reset("piracy")
    assert "piracy" in caplog.text


def test_texts_follow_the_language(tmp_path: Path) -> None:
    desktop = Desktop(tmp_path, None, language="fr")
    desktop.core.start()
    try:
        desktop.core.ready()
        view = desktop.views.wait_for(lambda v: True)
    finally:
        desktop.core.stop()
    assert view["language"] == "fr"
    assert blocks(view)["mining"]["status"] == "Aucune session de minage"


def test_the_activities_shown_come_from_the_settings_file(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.json").write_text(
        json.dumps(
            {
                "edrockmaster.display.activities": '["engineering", "mining"]',
                "edrockmaster.display.offered": '["mining", "combat", "trade", "engineering"]',
            }
        ),
        encoding="utf-8",
    )
    desktop = Desktop(tmp_path, None)
    desktop.core.start()
    try:
        desktop.core.ready()
        view = desktop.views.wait_for(lambda v: True)
    finally:
        desktop.core.stop()
    assert [block["activity"] for block in view["activities"]] == ["mining", "engineering"]


def test_local_data_reset_shows_a_notice_until_dismissed(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "edrockmaster.sqlite3").write_bytes(b"not a database" * 100)
    desktop = Desktop(tmp_path, None)
    desktop.core.start()
    desktop.core.ready()
    try:
        desktop.views.wait_for(lambda v: v["notice"] == "reset")
        desktop.core.dismiss_notice()
        desktop.views.wait_for(lambda v: v["notice"] is None)
    finally:
        desktop.core.stop()
    database = desktop.core.database
    assert database is not None
    assert not database.is_open


def test_a_failing_entry_or_push_is_logged_and_the_core_goes_on(
    tmp_path: Path, journal: Path, caplog: pytest.LogCaptureFixture
) -> None:
    desktop = Desktop(tmp_path, journal)
    failures = {"push": 1}

    def push(view: dict[str, Any]) -> None:
        if failures["push"]:
            failures["push"] -= 1
            raise ConnectionError("window closed")
        desktop.views.push(view)

    desktop.core._push = push
    desktop.core.start()
    try:
        companion = desktop.core.companion
        assert companion is not None
        original = companion.handle_journal_entry

        def broken(entry: Any, is_beta: bool) -> Any:
            if entry["event"] == "Music":
                raise ValueError("unexpected entry")
            return original(entry, is_beta)

        companion.handle_journal_entry = broken  # type: ignore[method-assign]
        with caplog.at_level(logging.ERROR):
            desktop.core.ready()
            write_journal(journal, TRADE, chunk=10_000)
            desktop.views.wait_for(lambda v: v["current"] == "trade")
    finally:
        desktop.core.stop()
    assert "window closed" in caplog.text
    assert "Music" in caplog.text


def test_calls_before_start_are_refused(tmp_path: Path) -> None:
    desktop = Desktop(tmp_path, None)
    with pytest.raises(RuntimeError, match="not started"):
        desktop.core._send()


def test_unavailable_local_data_shows_a_notice(tmp_path: Path) -> None:
    desktop = Desktop(tmp_path, None)
    (tmp_path / "data").write_text("a file where the data directory should be")
    desktop.core.start()
    desktop.core.ready()
    try:
        desktop.views.wait_for(lambda v: v["notice"] == "unavailable")
    finally:
        desktop.core.stop()


def test_stopping_before_starting_is_harmless(tmp_path: Path) -> None:
    Desktop(tmp_path, None).core.stop()


def test_nothing_is_pushed_before_the_interface_is_ready(desktop: Desktop, journal: Path) -> None:
    write_journal(journal, TRADE, chunk=10_000)
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        time.sleep(0.05)
    assert desktop.views.received == []
    desktop.core.ready()
    view = desktop.views.wait_for(lambda v: v["current"] == "trade")
    assert view["journal"]["file"] == "Journal.2026-10-08T014139.01.log"


def test_resets_and_the_first_view_shown_are_logged(
    desktop: Desktop, journal: Path, caplog: pytest.LogCaptureFixture
) -> None:
    desktop.core.ready()
    with caplog.at_level(logging.INFO):
        desktop.core.reset("mining")
        desktop.core.shown()
        write_journal(journal, TRADE, chunk=10_000)
        desktop.views.wait_for(lambda v: blocks(v)["trade"]["canReset"])
        desktop.core.reset("trade")
        desktop.views.wait_for(lambda v: "reset" in blocks(v)["trade"]["status"])
    assert "Reset of mining: no session" in caplog.text
    assert "Reset of trade: session ended" in caplog.text
    assert "The interface shows the live view" in caplog.text
