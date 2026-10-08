"""Where the game writes its journal, and which journal file is the current one (ADR 0020).

The game writes one ``Journal.<start>.<part>.log`` per game session, in the
"Saved Games" folder of the player's Windows profile; on Linux, inside the
Proton prefix of the game. A long session continues in a new part (``.02``)
after a ``Continue`` event. File names carry their start time, in two formats:
``Journal.2026-10-08T014139.01.log`` (since 2022) and ``Journal.220315152335.01.log``.
"""

from __future__ import annotations

import ctypes
import re
import sys
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from pathlib import Path
from uuid import UUID

GAME_FOLDER = Path("Frontier Developments") / "Elite Dangerous"
STEAM_APP_ID = 359320
"""Elite Dangerous on Steam: its Proton prefix is named after it."""

_JOURNAL_NAME = re.compile(
    r"^Journal(?P<beta>Alpha|Beta)?\."
    r"(?P<start>\d{4}-\d{2}-\d{2}T\d{6}|\d{12})\.(?P<part>\d{2})\.log$"
)


def journal_files(directory: Path) -> list[Path]:
    """The journal files of a folder, oldest first (by the start time in their name, then part)."""
    found = []
    try:
        entries = list(directory.iterdir())
    except OSError:
        return []
    for path in entries:
        key = _sort_key(path.name)
        if key is not None:
            found.append((key, path))
    return [path for _, path in sorted(found)]


def newest_journal(directory: Path) -> Path | None:
    files = journal_files(directory)
    return files[-1] if files else None


def is_beta_file(path: Path) -> bool:
    match = _JOURNAL_NAME.match(path.name)
    return bool(match and match["beta"])


def _sort_key(name: str) -> tuple[datetime, int] | None:
    match = _JOURNAL_NAME.match(name)
    if match is None:
        return None
    start = match["start"]
    try:
        if "T" in start:
            moment = datetime.strptime(start, "%Y-%m-%dT%H%M%S")
        else:
            moment = datetime.strptime(start, "%y%m%d%H%M%S")
    except ValueError:
        return None
    return moment, int(match["part"])


def default_journal_folder(
    platform: str = sys.platform,
    home: Path | None = None,
    saved_games: Callable[[], Path | None] | None = None,
) -> Path | None:
    """The journal folder where the game usually writes it, if it exists."""
    home = home if home is not None else Path.home()
    return next((path for path in _candidates(platform, home, saved_games) if path.is_dir()), None)


def _candidates(
    platform: str, home: Path, saved_games: Callable[[], Path | None] | None
) -> Iterable[Path]:
    if platform == "win32":
        known = (saved_games or _windows_saved_games)()
        if known is not None:
            yield known / GAME_FOLDER
        yield home / "Saved Games" / GAME_FOLDER
    else:
        user = Path("drive_c") / "users" / "steamuser" / "Saved Games" / GAME_FOLDER
        for steam in (
            home / ".steam" / "steam",
            home / ".local" / "share" / "Steam",
            home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
        ):
            yield steam / "steamapps" / "compatdata" / str(STEAM_APP_ID) / "pfx" / user


def _windows_saved_games() -> Path | None:  # pragma: no cover - Windows only
    """The "Saved Games" known folder, wherever the player moved it."""
    from ctypes import wintypes  # noqa: PLC0415 - Windows types, for Windows only

    class _Guid(ctypes.Structure):
        _fields_ = [("data", ctypes.c_byte * 16)]

    folder = _Guid()
    folder.data[:] = UUID("4C5C32FF-BB9D-43B0-B5B4-2D72E54EAAA4").bytes_le  # FOLDERID_SavedGames
    path = wintypes.LPWSTR()
    shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
    if shell32.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(path)) != 0:
        return None
    try:
        return Path(path.value) if path.value else None
    finally:
        ctypes.windll.ole32.CoTaskMemFree(path)  # type: ignore[attr-defined]


def environment_override(environ: Mapping[str, str]) -> Path | None:
    """``EDROCKMASTER_JOURNAL_DIR``: a folder set by hand, for tests and unusual installs."""
    value = environ.get("EDROCKMASTER_JOURNAL_DIR", "")
    return Path(value) if value else None
