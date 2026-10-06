import json

import pytest

from edrockmaster.application.build import (
    BuildFileError,
    BuildInfo,
    Channel,
    build_file_content,
    development_build,
    parse_build_file,
)

BASE = "0.3.0"
COMMIT = "2606b47c3f1a9e8d7c6b5a4f3e2d1c0b9a8f7e6d"


def build_json(**fields: object) -> str:
    return json.dumps({"version": "0.3.0-rc.2", "commit": COMMIT, "channel": "candidate"} | fields)


def test_a_clone_without_build_file_is_a_development_build() -> None:
    build = development_build(BASE)
    assert build == BuildInfo(version="0.3.0-dev", channel=Channel.DEV, commit=None)
    assert build.short_commit is None


@pytest.mark.parametrize(
    ("version", "channel"),
    [
        ("0.3.0", "production"),
        ("0.3.0-rc.2", "candidate"),
        ("0.3.0-rc.12", "candidate"),
        ("0.3.0-dev+2606b47", "dev"),
        ("0.3.0-dev", "dev"),
    ],
)
def test_valid_build_files_are_read(version: str, channel: str) -> None:
    build = parse_build_file(build_json(version=version, channel=channel), BASE)
    assert build == BuildInfo(version=version, channel=Channel(channel), commit=COMMIT)
    assert build.short_commit == "2606b47"


def test_the_commit_is_optional() -> None:
    text = json.dumps({"version": "0.3.0", "channel": "production"})
    assert parse_build_file(text, BASE).commit is None


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not json",
        "[]",
        build_json(version=3),
        build_json(channel="beta"),
        build_json(commit="xyz"),
        build_json(commit=42),
        # Another base version than the code's: files from two builds mixed up
        build_json(version="0.2.2-rc.1"),
        # A channel the version does not match
        build_json(version="0.3.0", channel="candidate"),
        build_json(version="0.3.0-rc.2", channel="production"),
        build_json(version="0.3.0-rc.0", channel="candidate"),
        build_json(version="0.3.0-rc.2", channel="dev"),
        build_json(version="0.3.0+2606b47", channel="dev"),
        build_json(version="0.3.0-dev+", channel="dev"),
    ],
)
def test_invalid_build_files_are_refused(text: str) -> None:
    with pytest.raises(BuildFileError):
        parse_build_file(text, BASE)


def test_the_build_file_written_by_the_packaging_reads_back() -> None:
    text = build_file_content("0.3.0-rc.2", "candidate", COMMIT, BASE)
    assert parse_build_file(text, BASE) == BuildInfo("0.3.0-rc.2", Channel.CANDIDATE, COMMIT)


def test_the_packaging_refuses_to_write_an_invalid_build_file() -> None:
    with pytest.raises(BuildFileError):
        build_file_content("0.3.0-rc.2", "production", COMMIT, BASE)
