import json
import logging
from pathlib import Path

import pytest

from edrockmaster.application.build import BuildInfo, Channel
from edrockmaster.infrastructure.build_file import load_build

logger = logging.getLogger("test.build_file")
COMMIT = "2606b47c3f1a9e8d7c6b5a4f3e2d1c0b9a8f7e6d"


def test_the_build_file_of_the_package_gives_the_build(tmp_path: Path) -> None:
    (tmp_path / "build.json").write_text(
        json.dumps({"version": "0.3.0-rc.2", "commit": COMMIT, "channel": "candidate"}),
        encoding="utf-8",
    )
    assert load_build(tmp_path, "0.3.0", logger) == BuildInfo(
        "0.3.0-rc.2", Channel.CANDIDATE, COMMIT
    )


def test_without_build_file_it_is_a_development_build(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    assert load_build(tmp_path, "0.3.0", logger) == BuildInfo("0.3.0-dev", Channel.DEV)
    assert not caplog.records


def test_an_invalid_build_file_is_logged_not_fatal(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "build.json").write_text("{", encoding="utf-8")
    assert load_build(tmp_path, "0.3.0", logger) == BuildInfo("0.3.0-dev", Channel.DEV)
    assert "Ignoring the build file" in caplog.text


def test_an_unreadable_build_file_is_logged_not_fatal(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "build.json").mkdir()
    assert load_build(tmp_path, "0.3.0", logger) == BuildInfo("0.3.0-dev", Channel.DEV)
    assert "Ignoring the build file" in caplog.text
