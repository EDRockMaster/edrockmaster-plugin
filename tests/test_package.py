"""The packaging: the zip players install, with its build file (ADR 0016)."""

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from edrockmaster import VERSION
from tests.scripts import load_script

ROOT = Path(__file__).resolve().parent.parent
build_file = load_script("build_file")


def head_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


# The plugin is packaged by a shell script, on Gitea's Linux runner
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="package.sh is a shell script")


@posix_only
def test_the_zip_carries_a_build_file_matching_the_release(tmp_path: Path) -> None:
    version = f"{VERSION}-rc.3"
    subprocess.run(
        ["scripts/package.sh", version, "candidate", str(tmp_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    with zipfile.ZipFile(tmp_path / f"EDRockMaster-v{version}.zip") as archive:
        build = json.loads(archive.read("EDRockMaster/edrockmaster/build.json"))
        assert "EDRockMaster/load.py" in archive.namelist()
        # Game data of Frontier, with the notice that says so (ADR 0017)
        assert "EDRockMaster/edrockmaster/domain/engineering/catalogue.json" in archive.namelist()
        assert "EDRockMaster/NOTICE" in archive.namelist()
    assert build == {"version": version, "commit": head_commit(), "channel": "candidate"}


@posix_only
def test_the_packaging_refuses_a_build_the_plugin_would_refuse(tmp_path: Path) -> None:
    result = subprocess.run(
        ["scripts/package.sh", f"{VERSION}-rc.3", "production", str(tmp_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "refused" in result.stderr


def test_the_build_file_script_prints_the_file(capsys: pytest.CaptureFixture[str]) -> None:
    commit = "2606b47c3f1a9e8d7c6b5a4f3e2d1c0b9a8f7e6d"
    assert build_file.main([VERSION, "production", commit]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "version": VERSION,
        "commit": commit,
        "channel": "production",
    }


def test_the_build_file_script_needs_three_arguments() -> None:
    assert build_file.main([VERSION]) == 2
