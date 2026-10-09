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
            usual_journal_folder=lambda: None,
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


def test_the_live_view_carries_the_situation(desktop: Desktop, journal: Path) -> None:
    desktop.core.ready()
    write_journal(journal, "engineering-power-distributor-2026-10-08.jsonl", chunk=10_000)
    # The game closed at Marco Qwent's base, after the rolls
    view = desktop.views.wait_for(
        lambda v: v["situation"]["system"] is not None and not v["situation"]["gameRunning"]
    )
    assert view["situation"]["system"] == "Sirius"
    assert view["situation"]["station"] == "Qwent Research Base"


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


# Engineering goals (ADR 0017)

FSD_GOAL = {"kind": "blueprint", "module": "fsd", "name": "FSD_LongRange", "grade": 5, "count": 2}


def goals(view: dict[str, Any]) -> list[dict[str, Any]]:
    return list(view["engineering"]["goals"])


def test_goals_added_changed_and_removed_from_the_interface(desktop: Desktop) -> None:
    desktop.core.ready()
    desktop.core.add_goal(FSD_GOAL)
    [goal] = goals(desktop.views.wait_for(lambda v: len(goals(v)) == 1))
    assert (goal["kind"], goal["grade"], goal["count"]) == ("blueprint", 5, 2)
    desktop.core.change_goal(goal["id"], 3)
    desktop.views.wait_for(lambda v: [g["count"] for g in goals(v)] == [3])
    desktop.core.remove_goal(goal["id"])
    desktop.views.wait_for(lambda v: goals(v) == [])


def test_goal_requests_that_cannot_be_done_are_logged(
    desktop: Desktop, caplog: pytest.LogCaptureFixture
) -> None:
    desktop.core.ready()
    with caplog.at_level(logging.WARNING):
        desktop.core.add_goal({**FSD_GOAL, "grade": 9})
        desktop.core.change_goal("nowhere", 2)
        desktop.core.remove_goal("nowhere")
        desktop.core.add_goal(FSD_GOAL)
        [goal] = goals(desktop.views.wait_for(lambda v: len(goals(v)) == 1))
        desktop.core.change_goal(goal["id"], 0)
        # The core handles calls in order: once this one is seen, the others were
        desktop.core.add_goal(FSD_GOAL)
        desktop.views.wait_for(lambda v: len(goals(v)) == 2)
    assert "Goal refused" in caplog.text
    assert "No goal 'nowhere' to change" in caplog.text
    assert "No goal 'nowhere' to remove" in caplog.text
    assert "Goal change refused" in caplog.text


def test_the_goal_form_s_catalogue_once_started(tmp_path: Path) -> None:
    desktop = Desktop(tmp_path, None)
    with pytest.raises(RuntimeError, match="not started"):
        desktop.core.catalogue()
    desktop.core.start()
    try:
        assert len(desktop.core.catalogue()["modules"]) == 44
    finally:
        desktop.core.stop()
    with pytest.raises(RuntimeError, match="not started"):
        Desktop(tmp_path, None).core._require_names()


# Settings (ADR 0020)


def test_settings_saved_from_the_interface_apply_and_are_kept(tmp_path: Path) -> None:
    desktop = Desktop(tmp_path, None)
    desktop.core.start()
    try:
        desktop.core.ready()
        desktop.views.wait_for(lambda v: v["language"] == "en")
        request = desktop.core.settings()
        request.update(activities=["engineering"], language="fr", sound=False)
        desktop.core.save_settings(request)
        view = desktop.views.wait_for(lambda v: v["language"] == "fr")
        assert [block["activity"] for block in view["activities"]] == ["engineering"]
        assert blocks(view)["engineering"]["status"] == "Aucune session d'ingénierie"
        assert desktop.core.catalogue()["modules"][0]["name"] != ""
        assert desktop.core.settings()["language"] == "fr"
    finally:
        desktop.core.stop()
    stored = json.loads((tmp_path / "data" / "settings.json").read_text(encoding="utf-8"))
    assert stored["edrockmaster.desktop.language"] == "fr"
    assert stored["edrockmaster.sound"] is False


def test_invalid_settings_are_logged_and_change_nothing(
    desktop: Desktop, caplog: pytest.LogCaptureFixture
) -> None:
    desktop.core.ready()
    request = desktop.core.settings()
    with caplog.at_level(logging.WARNING):
        desktop.core.save_settings({**request, "language": "de"})
        desktop.core.save_settings({**request, "sound": False})
        # The core thread runs in order: the first view, the refusal, then the valid change's view
        desktop.views.wait_for(lambda v: len(desktop.views.received) >= 2)
    assert "Settings refused: language" in caplog.text


def test_the_journal_folder_of_the_settings_is_used_from_the_next_start(
    tmp_path: Path, journal: Path, caplog: pytest.LogCaptureFixture
) -> None:
    first = Desktop(tmp_path, None)
    first.core.start()
    try:
        first.core.ready()
        request = first.core.settings()
        assert request["journalFolderInUse"] is None
        with caplog.at_level(logging.INFO):
            first.core.save_settings({**request, "journalFolder": str(journal)})
            first.views.wait_for(lambda v: True)
            first.core.stop()
    finally:
        first.core.stop()
    assert "used from the next start" in caplog.text
    write_journal(journal, TRADE, chunk=10_000)
    second = Desktop(tmp_path, None)
    second.core.start()
    try:
        second.core.ready()
        second.views.wait_for(lambda v: v["journal"]["folder"] == str(journal))
    finally:
        second.core.stop()


def test_settings_before_start_are_refused(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not started"):
        Desktop(tmp_path, None).core.settings()
