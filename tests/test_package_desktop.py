"""Packaging of the desktop application for Windows (ADR 0022): the parts that run anywhere."""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from tests.scripts import load_script

packager = load_script("package_desktop")
icons = load_script("make_icons")
Identity = packager.Identity
FOUNDATION = "{http://schemas.microsoft.com/appx/manifest/foundation/windows10}"


def template() -> str:
    return str(packager.MANIFEST_TEMPLATE.read_text(encoding="utf-8"))


def test_the_manifest_carries_the_identity_and_the_version() -> None:
    identity = Identity(
        "Nexagone.EDRockMasterCompanion",
        'CN=ABCD-1234 "x"',
        "DamScan & co",
        "EDRockMaster Companion",
    )
    root = ET.fromstring(packager.manifest(template(), identity, "0.4.3.0"))
    found = root.find(f"{FOUNDATION}Identity")
    assert found is not None
    assert found.attrib["Name"] == "Nexagone.EDRockMasterCompanion"
    assert found.attrib["Publisher"] == 'CN=ABCD-1234 "x"'
    assert found.attrib["Version"] == "0.4.3.0"
    assert (
        root.findtext(f"{FOUNDATION}Properties/{FOUNDATION}PublisherDisplayName") == "DamScan & co"
    )


def test_the_manifest_keeps_the_data_folder_unvirtualized() -> None:
    text = packager.manifest(template(), Identity.from_environment({}), "0.4.0.0")
    assert r"$(KnownFolder:LocalAppData)\EDRockMaster" in text
    assert 'Name="unvirtualizedResources"' in text
    assert 'Name="runFullTrust"' in text
    assert 'Executable="EDRockMaster\\EDRockMaster.exe"' in text


def test_a_development_identity_without_partner_center() -> None:
    identity = Identity.from_environment({"EDROCKMASTER_MSIX_NAME": ""})
    assert identity.name == "EDRockMaster.Development"
    assert identity.publisher.startswith("CN=")
    assert identity.display_name == "EDRockMaster"


@pytest.mark.parametrize("version", ["0.4.0", "0.4.3.1", "0.4.x.0", "v0.4.3.0"])
def test_only_store_versions_are_accepted(version: str) -> None:
    with pytest.raises(packager.PackagingError, match="MSIX version"):
        packager.manifest(template(), Identity.from_environment({}), version)


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


def test_the_msix_layout(tmp_path: Path) -> None:
    app = tmp_path / "app"
    app.mkdir()
    (app / "EDRockMaster.exe").write_bytes(b"MZ")
    assets = tmp_path / "assets"
    icons.write(assets)
    layout = tmp_path / "msix"
    layout.mkdir()
    (layout / "stale").write_text("from a previous build")
    packager.msix_layout(app, assets, "<Package/>", layout)
    found = sorted(
        str(path.relative_to(layout)).replace("\\", "/")
        for path in layout.rglob("*")
        if path.is_file()
    )
    assert found[:2] == ["AppxManifest.xml", "EDRockMaster/EDRockMaster.exe"]
    logos = [name for name in found if name.startswith("assets/")]
    assert {
        "assets/Square150x150Logo.png",
        "assets/Square44x44Logo.png",
        "assets/StoreLogo.png",
    } <= set(logos)
    assert "assets/Square44x44Logo.targetsize-16_altform-unplated.png" in logos
    # The Store listing's images are uploaded apart, not packaged
    assert not any("store" in name for name in found)


def test_makeappx_is_the_newest_of_the_sdk(tmp_path: Path) -> None:
    for version in ("10.0.22621.0", "10.0.26100.0"):
        tool = tmp_path / "10" / "bin" / version / "x64" / "makeappx.exe"
        tool.parent.mkdir(parents=True)
        tool.write_bytes(b"MZ")
    assert packager.find_makeappx(tmp_path).parts[-3] == "10.0.26100.0"
    with pytest.raises(packager.PackagingError, match="Windows SDK"):
        packager.find_makeappx(tmp_path / "nowhere")


def test_icons_in_every_size_the_package_asks(tmp_path: Path) -> None:
    written = icons.write(tmp_path)
    sizes = {path.name: Image.open(path).size for path in written if path.suffix == ".png"}
    assert sizes["Square44x44Logo.png"] == (44, 44)
    assert sizes["Square150x150Logo.png"] == (150, 150)
    assert sizes["StoreLogo.png"] == (50, 50)
    for size in (16, 24, 32, 48, 256):
        assert sizes[f"Square44x44Logo.targetsize-{size}.png"] == (size, size)
        unplated = Image.open(tmp_path / f"Square44x44Logo.targetsize-{size}_altform-unplated.png")
        corner = unplated.getpixel((0, 0))
        assert isinstance(corner, tuple)
        assert corner[3] == 0  # the rock alone, on a transparent background
    assert (tmp_path / "EDRockMaster.ico").stat().st_size > 0


def test_the_store_listing_s_images(tmp_path: Path) -> None:
    icons.write(tmp_path)
    store = tmp_path / "store"
    assert {path.name: Image.open(path).size for path in store.glob("*.png")} == {
        "app-tile-300.png": (300, 300),
        "box-art-1080.png": (1080, 1080),
        "box-art-2160.png": (2160, 2160),
        "poster-720x1080.png": (720, 1080),
    }


def test_a_font_is_always_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(icons, "FONTS", ("/nowhere/font.ttf",))
    assert icons._font(20) is not None


def test_icons_usage(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert icons.main([]) == 2
    assert icons.main([str(tmp_path)]) == 0
    assert "StoreLogo.png" in capsys.readouterr().out
