"""Package the desktop application for Windows (ADR 0020, ADR 0022).

Builds, in ``<dist>``:

- ``EDRockMaster-v<version>-windows.zip``: the portable application, one folder;
- ``EDRockMaster-v<version>.msix``: the package for the Microsoft Store, which signs it.

Runs on Windows (PyInstaller does not cross-compile; ``makeappx`` comes with the Windows
SDK). The interface must be built first (``pnpm build`` in ``web/``). The package
identity comes from the environment, as Partner Center gives it when the name is
reserved; a development identity is used without it:

- ``EDROCKMASTER_MSIX_NAME``: Package/Identity/Name;
- ``EDROCKMASTER_MSIX_PUBLISHER``: Package/Identity/Publisher (``CN=…``);
- ``EDROCKMASTER_MSIX_PUBLISHER_NAME``: Package/Properties/PublisherDisplayName.

Usage: python scripts/package_desktop.py <version> <channel> <msix version> [<dist>]
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from edrockmaster import VERSION  # noqa: E402 - the repository's root is put on the path first
from edrockmaster.application.build import BuildFileError, build_file_content  # noqa: E402

SPEC = ROOT / "packaging" / "windows" / "EDRockMaster.spec"
MANIFEST_TEMPLATE = ROOT / "packaging" / "windows" / "AppxManifest.xml.in"
INTERFACE = ROOT / "edrockmaster" / "desktop" / "interface" / "index.html"
BUILD_FILE = ROOT / "edrockmaster" / "build.json"
APP_FOLDER = "EDRockMaster"
WINDOWS_KITS = Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Windows Kits"


class PackagingError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Identity:
    name: str
    publisher: str
    publisher_name: str

    @classmethod
    def from_environment(cls, environ: Mapping[str, str]) -> Identity:
        return cls(
            environ.get("EDROCKMASTER_MSIX_NAME") or "EDRockMaster.Development",
            environ.get("EDROCKMASTER_MSIX_PUBLISHER") or "CN=EDRockMaster Development",
            environ.get("EDROCKMASTER_MSIX_PUBLISHER_NAME") or "EDRockMaster (development)",
        )


def manifest(template: str, identity: Identity, msix_version: str) -> str:
    """The MSIX manifest, its placeholders filled (values escaped for XML attributes)."""
    parts = msix_version.split(".")
    if len(parts) != 4 or not all(part.isdigit() for part in parts) or parts[3] != "0":
        raise PackagingError(f"{msix_version!r} is not an MSIX version for the Store (X.Y.Z.0)")
    return template.format(
        name=escape(identity.name, {'"': "&quot;"}),
        publisher=escape(identity.publisher, {'"': "&quot;"}),
        publisher_name=escape(identity.publisher_name),
        version=msix_version,
    )


def portable_zip(app: Path, target: Path) -> Path:
    """The application folder as a zip: ``EDRockMaster/…``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(app.rglob("*")):
            if path.is_file():
                archive.write(path, Path(APP_FOLDER) / path.relative_to(app))
    return target


def msix_layout(app: Path, assets: Path, manifest_text: str, layout: Path) -> Path:
    """The folder ``makeappx`` packs: the manifest, the assets, the application folder."""
    if layout.exists():
        shutil.rmtree(layout)
    shutil.copytree(app, layout / APP_FOLDER)
    (layout / "assets").mkdir(parents=True)
    for name in ("Square44x44Logo.png", "Square150x150Logo.png", "StoreLogo.png"):
        shutil.copy2(assets / name, layout / "assets" / name)
    (layout / "AppxManifest.xml").write_text(manifest_text, encoding="utf-8")
    return layout


def find_makeappx(kits: Path = WINDOWS_KITS) -> Path:
    """The newest ``makeappx.exe`` of the Windows SDK, for x64."""
    found = sorted(kits.glob("10/bin/*/x64/makeappx.exe"))
    if not found:
        raise PackagingError(f"makeappx.exe not found under {kits}: install the Windows SDK")
    return found[-1]


def head_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def package(
    version: str, channel: str, msix_version: str, dist: Path
) -> list[Path]:  # pragma: no cover - Windows
    """The whole packaging, on Windows."""
    if not INTERFACE.is_file():
        raise PackagingError(f"{INTERFACE} missing: run 'pnpm build' in web/ first")
    try:
        BUILD_FILE.write_text(
            build_file_content(version, channel, head_commit(), VERSION), encoding="utf-8"
        )
    except BuildFileError as error:
        raise PackagingError(str(error)) from error
    manifest_text = manifest(
        MANIFEST_TEMPLATE.read_text(encoding="utf-8"),
        Identity.from_environment(os.environ),
        msix_version,
    )
    assets = dist / "assets"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "make_icons.py"), str(assets)], check=True
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(SPEC),
            "--noconfirm",
            "--distpath",
            str(dist / "pyinstaller"),
            "--workpath",
            str(dist / "work"),
        ],
        check=True,
    )
    app = dist / "pyinstaller" / APP_FOLDER
    archive = portable_zip(app, dist / f"EDRockMaster-v{version}-windows.zip")
    layout = msix_layout(app, assets, manifest_text, dist / "msix")
    msix = dist / f"EDRockMaster-v{version}.msix"
    subprocess.run(
        [str(find_makeappx()), "pack", "/d", str(layout), "/p", str(msix), "/o"], check=True
    )
    return [archive, msix]


def main(arguments: list[str]) -> int:  # pragma: no cover - Windows
    if len(arguments) not in (3, 4):
        print(__doc__, file=sys.stderr)
        return 2
    version, channel, msix_version = arguments[:3]
    dist = Path(arguments[3]) if len(arguments) == 4 else ROOT / "dist-desktop"
    try:
        for path in package(version, channel, msix_version, dist):
            print(path)
    except PackagingError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
