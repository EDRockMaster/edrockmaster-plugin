import sys
from pathlib import Path

import pytest

from edrockmaster.infrastructure.paths import data_directory

HOME = Path("/home/cmdr")


def test_windows_uses_local_app_data() -> None:
    environ = {"LOCALAPPDATA": r"C:\Users\cmdr\AppData\Local"}
    path = data_directory(platform="win32", environ=environ, home=HOME)
    assert path == Path(r"C:\Users\cmdr\AppData\Local") / "EDRockMaster"


def test_windows_without_local_app_data_falls_back_to_the_profile() -> None:
    path = data_directory(platform="win32", environ={}, home=HOME)
    assert path == HOME / "AppData" / "Local" / "EDRockMaster"


def test_macos_uses_application_support() -> None:
    path = data_directory(platform="darwin", environ={}, home=HOME)
    assert path == HOME / "Library" / "Application Support" / "EDRockMaster"


@pytest.mark.skipif(sys.platform == "win32", reason="a Linux absolute path is not one on Windows")
def test_linux_honours_xdg_data_home() -> None:
    path = data_directory(platform="linux", environ={"XDG_DATA_HOME": "/data/xdg"}, home=HOME)
    assert path == Path("/data/xdg/EDRockMaster")


@pytest.mark.parametrize("xdg", ["", "relative/path"])
def test_linux_ignores_an_empty_or_relative_xdg_data_home(xdg: str) -> None:
    path = data_directory(platform="linux", environ={"XDG_DATA_HOME": xdg}, home=HOME)
    assert path == HOME / ".local" / "share" / "EDRockMaster"
