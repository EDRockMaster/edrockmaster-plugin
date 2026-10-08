import json
import logging
import threading
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from edrockmaster.application.build import BuildInfo, Channel
from edrockmaster.application.companion import Notification
from edrockmaster.domain.engineering.goals import BlueprintGoal, Goal, GoalId
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.mining.prospecting import ProspectorAlertRaised
from edrockmaster.domain.mining.session import SessionStarted
from edrockmaster.edmc.i18n import tl
from edrockmaster.edmc.plugin import PLUGIN_NAME, Plugin, plugin_logger_name
from edrockmaster.infrastructure.database import WrongThreadError
from edrockmaster.infrastructure.worker import THREAD_NAME
from tests.fakes import FakeConfig

PROSPECTED: Entry = {
    "timestamp": "2026-10-03T12:00:00Z",
    "event": "ProspectedAsteroid",
    "Materials": [{"Name": "Painite", "Proportion": 40.0}],
    "Content": "$AsteroidMaterialContent_High;",
    "Remaining": 100.0,
}


class Started:
    def __init__(self, tmp_path: Path, config: FakeConfig | None = None) -> None:
        self.data_dir = tmp_path / "data"
        self.plugin = Plugin(config or FakeConfig(), data_directory=lambda: self.data_dir)
        self.name = self.plugin.start(str(tmp_path / "plugins" / "EDRockMaster"))

    def entry(self, entry: Entry, is_beta: bool = False) -> str | None:
        return self.plugin.journal_entry("Cmdr", is_beta, "Sol", None, entry, {})


@pytest.fixture
def started(tmp_path: Path) -> Iterator[Started]:
    started = Started(tmp_path)
    yield started
    started.plugin.stop()


def io_threads() -> list[threading.Thread]:
    return [thread for thread in threading.enumerate() if thread.name == THREAD_NAME]


def test_start_names_the_plugin_and_starts_the_io_thread(started: Started) -> None:
    assert started.name == PLUGIN_NAME
    assert io_threads()


def test_plugin_dir_may_be_a_path(tmp_path: Path) -> None:
    plugin = Plugin(FakeConfig(), data_directory=lambda: tmp_path)
    assert plugin.start(tmp_path) == PLUGIN_NAME
    plugin.stop()


COMMIT = "2606b47c3f1a9e8d7c6b5a4f3e2d1c0b9a8f7e6d"


def write_build_file(plugin_dir: Path) -> None:
    (plugin_dir / "edrockmaster").mkdir(parents=True)
    (plugin_dir / "edrockmaster" / "build.json").write_text(
        json.dumps({"version": "0.3.0-rc.2", "commit": COMMIT, "channel": "candidate"}),
        encoding="utf-8",
    )


def test_the_build_comes_from_the_build_file_of_the_package(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    plugin_dir = tmp_path / "plugins" / "EDRockMaster"
    write_build_file(plugin_dir)
    plugin = Plugin(FakeConfig({"edrockmaster.record_journal": True}), lambda: tmp_path / "data")
    with caplog.at_level(logging.INFO):
        plugin.start(plugin_dir)
    plugin.journal_entry("Cmdr", False, "Sol", None, PROSPECTED, {})
    plugin.stop()
    assert plugin.build == BuildInfo("0.3.0-rc.2", Channel.CANDIDATE, COMMIT)
    assert "EDRockMaster 0.3.0-rc.2 (candidate, commit 2606b47) started" in caplog.text
    [recording] = (tmp_path / "data" / "recordings").glob("journal-*.jsonl")
    assert recording.name.endswith("-0.3.0-rc.2.jsonl")


def test_a_clone_is_a_development_build(started: Started) -> None:
    assert started.plugin.build.channel is Channel.DEV
    assert started.plugin.build.version.endswith("-dev")


def test_stop_ends_the_io_thread(started: Started) -> None:
    started.plugin.stop()
    assert not io_threads()


def test_entries_before_start_are_ignored() -> None:
    plugin = Plugin(FakeConfig())
    assert plugin.journal_entry("Cmdr", False, None, None, PROSPECTED, {}) is None
    plugin.stop()


def test_notifications_reach_the_subscribers(started: Started) -> None:
    received: list[Sequence[Notification]] = []
    started.plugin.subscribe(received.append)
    assert started.entry(PROSPECTED) is None
    [notifications] = received
    assert isinstance(notifications[0], SessionStarted)
    assert isinstance(notifications[-1], ProspectorAlertRaised)


def test_irrelevant_entries_notify_nobody(started: Started) -> None:
    received: list[Sequence[Notification]] = []
    started.plugin.subscribe(received.append)
    started.entry({"timestamp": "2026-10-03T12:00:00Z", "event": "Music"})
    assert received == []


def test_alert_sound_plays_once_attached(started: Started) -> None:
    played: list[None] = []
    started.entry(PROSPECTED)  # no sound attached yet: silently skipped
    started.plugin.attach_alert_sound(lambda: played.append(None))
    started.entry({**PROSPECTED, "timestamp": "2026-10-03T12:05:00Z"})
    assert played == [None]


def test_journal_is_recorded_in_the_data_directory_when_enabled(tmp_path: Path) -> None:
    started = Started(tmp_path, FakeConfig({"edrockmaster.record_journal": True}))
    started.entry(PROSPECTED, is_beta=True)
    started.plugin.stop()
    [recording] = (started.data_dir / "recordings").glob("journal-*.jsonl")
    lines = recording.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [{"is_beta": True, "entry": PROSPECTED}]


def test_a_failure_is_logged_and_reported_without_breaking_the_plugin(
    started: Started, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(_notifications: Sequence[Notification]) -> None:
        raise RuntimeError("boom")

    started.plugin.subscribe(broken)
    with caplog.at_level(logging.ERROR):
        error = started.entry(PROSPECTED)
    assert error == tl("EDRockMaster: internal error, see the EDMC log")
    assert "boom" in caplog.text
    received: list[Sequence[Notification]] = []
    started.plugin.subscribe(received.append)
    started.entry({**PROSPECTED, "timestamp": "2026-10-03T12:05:00Z"})
    assert received


def test_translation_falls_back_to_english_outside_edmc() -> None:
    assert tl("Mining session") == "Mining session"


def test_a_failing_use_case_is_logged_and_reported(
    started: Started, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(entry: Entry, is_beta: bool) -> list[Notification]:
        raise ValueError("unexpected entry")

    assert started.plugin.companion is not None
    monkeypatch.setattr(started.plugin.companion, "handle_journal_entry", broken)
    with caplog.at_level(logging.ERROR):
        error = started.entry(PROSPECTED)
    assert error == tl("EDRockMaster: internal error, see the EDMC log")
    assert "ProspectedAsteroid" in caplog.text


def test_logger_is_named_after_the_plugin_folder_as_edmc_expects() -> None:
    module = Path("/edmc/plugins/EDRockMaster/edrockmaster/edmc/plugin.py")
    assert plugin_logger_name("EDMarketConnector", module) == "EDMarketConnector.EDRockMaster"


# Local database (ADR 0018)


def flush_io(plugin: Plugin) -> None:
    done = threading.Event()
    plugin._worker.submit(done.set)
    assert done.wait(timeout=2)


def test_the_local_database_opens_on_the_io_thread_only(started: Started) -> None:
    flush_io(started.plugin)
    database = started.plugin.database
    assert database is not None
    assert database.path == started.data_dir / "edrockmaster.sqlite3"
    assert database.is_open
    assert database.owner == THREAD_NAME
    with pytest.raises(WrongThreadError):
        database.connection()


def test_the_local_database_is_closed_when_the_plugin_stops(started: Started) -> None:
    started.plugin.stop()
    database = started.plugin.database
    assert database is not None
    assert not database.is_open


def test_goals_are_stored_in_the_local_database(tmp_path: Path) -> None:
    goal = BlueprintGoal(GoalId.new(), "FSD_LongRange", "fsd", grade=5)
    first = Started(tmp_path)
    assert first.plugin.goals is not None
    first.plugin.goals.add(goal)
    first.plugin.stop()
    second = Started(tmp_path)
    try:
        assert second.plugin.goals is not None
        loaded: list[tuple[Goal, ...]] = []
        second.plugin.goals.load(loaded.append)
        flush_io(second.plugin)
        second.plugin._main_thread._run_pending()  # the panel's main loop, without a display
        assert loaded == [(goal,)]
    finally:
        second.plugin.stop()
