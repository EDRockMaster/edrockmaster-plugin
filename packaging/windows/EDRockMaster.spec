# PyInstaller specification of the desktop application for Windows (ADR 0020, ADR 0022).
# One folder (faster to start, fewer antivirus false alarms than one file), no console.
# Data files keep the places the code reads them from: next to their modules in the
# edrockmaster package, and L10n/ at the root, as in the repository.
# Run by scripts/package_desktop.py, which writes the build file and builds the interface first.
from pathlib import Path

ROOT = Path(SPECPATH).parents[1]
PACKAGE = ROOT / "edrockmaster"
ASSETS = Path(DISTPATH).parent / "assets"

a = Analysis(
    [str(PACKAGE / "desktop" / "__main__.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "L10n"), "L10n"),
        (str(PACKAGE / "build.json"), "edrockmaster"),
        (str(PACKAGE / "domain" / "engineering" / "catalogue.json"), "edrockmaster/domain/engineering"),
        (str(PACKAGE / "desktop" / "schemas"), "edrockmaster/desktop/schemas"),
        (str(PACKAGE / "desktop" / "interface" / "index.html"), "edrockmaster/desktop/interface"),
    ],
    # The plugin's Tk interface is not part of the desktop application
    excludes=["tkinter", "_tkinter", "edrockmaster.edmc", "edrockmaster.ui.panel", "edrockmaster.ui.preferences"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EDRockMaster",
    console=False,
    icon=str(ASSETS / "EDRockMaster.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="EDRockMaster")
