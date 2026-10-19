"""Packaging of the desktop application for Windows (ADR 0053): the parts that run anywhere."""

import re
import subprocess
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from tests.scripts import load_script

packager = load_script("package_desktop")
icons = load_script("make_icons")


def test_the_portable_zip_holds_one_folder(tmp_path: Path) -> None:
    app = tmp_path / "app"
    (app / "_internal").mkdir(parents=True)
    (app / "EDRockMaster.exe").write_bytes(b"MZ")
    (app / "_internal" / "python313.dll").write_bytes(b"dll")
    archive = packager.portable_zip(app, tmp_path / "dist" / "EDRockMaster-v0.4.0-windows.zip")
    with zipfile.ZipFile(archive) as opened:
        assert sorted(opened.namelist()) == [
            "EDRockMaster/EDRockMaster.exe",
            "EDRockMaster/_internal/python313.dll",
        ]


def test_the_icon_in_every_size_windows_asks(tmp_path: Path) -> None:
    [icon] = icons.write(tmp_path)
    assert icon.name == "EDRockMaster.ico"
    with Image.open(icon) as opened:
        assert opened.info["sizes"] == set(icons.ICO_SIZES)


def test_icons_usage(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert icons.main([]) == 2
    assert icons.main([str(tmp_path)]) == 0
    assert "EDRockMaster.ico" in capsys.readouterr().out


ROOT = Path(__file__).parents[1]
SPEC = ROOT / "packaging" / "windows" / "EDRockMaster.spec"


def bundled() -> list[Path]:
    """What the specification bundles from the package: ``PACKAGE / "a" / "b"`` entries."""
    entries = re.findall(r'PACKAGE((?:\s*/\s*"[^"]+")+)', SPEC.read_text(encoding="utf-8"))
    return [Path("edrockmaster", *re.findall(r'"([^"]+)"', entry)) for entry in entries]


def test_every_data_file_of_the_package_is_bundled() -> None:
    # A file the code reads beside its module, left out, stops the packaged application at start
    tracked = subprocess.run(
        ["git", "ls-files", "edrockmaster"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    data = [Path(name) for name in tracked if not name.endswith((".py", ".pyi", "py.typed"))]
    assert data
    sources = bundled()
    missing = [path for path in data if not any(path.is_relative_to(s) for s in sources)]
    assert missing == []
