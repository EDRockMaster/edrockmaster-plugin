import json
import logging
from pathlib import Path

import pytest

from edrockmaster.application.settings import DEFAULT_SETTINGS
from edrockmaster.infrastructure.settings_file import JsonFileConfig
from edrockmaster.infrastructure.settings_store import KeyValueSettingsStore
from edrockmaster.infrastructure.worker import Job

logger = logging.getLogger("test.settings_file")


def run_now(job: Job) -> None:
    job()


def test_settings_are_stored_as_the_plugin_stores_them(tmp_path: Path) -> None:
    path = tmp_path / "data" / "settings.json"
    store = KeyValueSettingsStore(JsonFileConfig(path, run_now, logger), logger)
    changed = DEFAULT_SETTINGS.__class__(
        alerts=DEFAULT_SETTINGS.alerts,
        sound_enabled=False,
        record_journal=True,
        display=DEFAULT_SETTINGS.display,
    )
    store.save(changed)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["edrockmaster.sound"] is False
    assert not path.with_name("settings.json.partial").exists()
    assert KeyValueSettingsStore(JsonFileConfig(path, run_now, logger), logger).load() == changed


def test_writes_happen_on_the_given_thread(tmp_path: Path) -> None:
    jobs: list[Job] = []
    config = JsonFileConfig(tmp_path / "settings.json", jobs.append, logger)
    config.set("edrockmaster.sound", True)
    assert not (tmp_path / "settings.json").exists()
    jobs[0]()
    assert (tmp_path / "settings.json").exists()


@pytest.mark.parametrize("content", ["{not json", "[1, 2]"])
def test_an_unreadable_file_gives_the_defaults(
    tmp_path: Path, content: str, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "settings.json"
    path.write_text(content, encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        config = JsonFileConfig(path, run_now, logger)
    assert config.get_str("edrockmaster.display.mode") is None
    assert "unreadable" in caplog.text


def test_values_of_another_type_are_the_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"a": "text", "b": True, "c": 3, "d": None}), encoding="utf-8")
    config = JsonFileConfig(path, run_now, logger)
    assert config.get_str("a") == "text"
    assert config.get_str("b", default="x") == "x"
    assert config.get_bool("a", default=True) is True
    assert config.get_bool("b") is True
    assert config.get_str("c") is None  # not kept
    assert config.get_bool("missing") is False
