"""Package the desktop application for Windows (ADR 0020, ADR 0053).

Builds, in ``<dist>``:

- ``pyinstaller/EDRockMaster/``: the application, one folder, which Velopack packs into
  its installer and its updates (``vpk pack``, in the Windows workflow);
- ``EDRockMaster-v<version>-windows.zip``: the same folder, for a quick check of a
  development build.

Runs on Windows (PyInstaller does not cross-compile). The interface must be built first
(``pnpm build`` in ``web/``).

Usage: python scripts/package_desktop.py <version> <channel> [<dist>]
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from edrockmaster import VERSION  # noqa: E402 - the repository's root is put on the path first
from edrockmaster.application.build import BuildFileError, build_file_content  # noqa: E402

SPEC = ROOT / "packaging" / "windows" / "EDRockMaster.spec"
INTERFACE = ROOT / "edrockmaster" / "desktop" / "interface" / "index.html"
BUILD_FILE = ROOT / "edrockmaster" / "build.json"
APP_FOLDER = "EDRockMaster"


class PackagingError(Exception):
    pass


def portable_zip(app: Path, target: Path) -> Path:
    """The application folder as a zip: ``EDRockMaster/…``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(app.rglob("*")):
            if path.is_file():
                archive.write(path, Path(APP_FOLDER) / path.relative_to(app))
    return target


def head_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def package(version: str, channel: str, dist: Path) -> list[Path]:  # pragma: no cover - Windows
    """The whole packaging, on Windows."""
    if not INTERFACE.is_file():
        raise PackagingError(f"{INTERFACE} missing: run 'pnpm build' in web/ first")
    try:
        BUILD_FILE.write_text(
            build_file_content(version, channel, head_commit(), VERSION), encoding="utf-8"
        )
    except BuildFileError as error:
        raise PackagingError(str(error)) from error
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
    return [app, portable_zip(app, dist / f"EDRockMaster-v{version}-windows.zip")]


def main(arguments: list[str]) -> int:  # pragma: no cover - Windows
    if len(arguments) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 2
    version, channel = arguments[:2]
    dist = Path(arguments[2]) if len(arguments) == 3 else ROOT / "dist-desktop"
    try:
        for path in package(version, channel, dist):
            print(path)
    except PackagingError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
