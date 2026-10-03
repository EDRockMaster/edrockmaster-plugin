"""Release consistency: one version everywhere, and a changelog entry for it."""

import re
import tomllib
from pathlib import Path

from edrockmaster import VERSION

ROOT = Path(__file__).resolve().parent.parent


def test_version_is_semantic() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION)


def test_package_and_project_versions_match() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == VERSION


def test_changelogs_describe_the_current_version() -> None:
    for name in ("CHANGELOG.md", "CHANGELOG.fr.md"):
        changelog = (ROOT / name).read_text(encoding="utf-8")
        assert f"## [{VERSION}]" in changelog, name
