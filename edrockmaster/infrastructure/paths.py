"""Where the application keeps its files: outside its install folder, so they survive updates."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

DIRECTORY_NAME = "EDRockMaster"


def data_directory(
    platform: str = sys.platform,
    environ: Mapping[str, str] = os.environ,
    home: Path | None = None,
) -> Path:
    """Return the application's data directory for the given platform (not created)."""
    home = home if home is not None else Path.home()
    if platform == "win32":
        local = environ.get("LOCALAPPDATA")
        base = Path(local) if local else home / "AppData" / "Local"
    elif platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        xdg = environ.get("XDG_DATA_HOME", "")
        # The XDG specification says relative paths must be ignored
        base = Path(xdg) if xdg and Path(xdg).is_absolute() else home / ".local" / "share"
    return base / DIRECTORY_NAME
