"""Opening a folder of the application in the platform's file manager.

The player opens the folder of the journal recordings or of the logs from the
*Settings* tab, to send a file with a bug report. On Windows the folder opens in
the Explorer; elsewhere the platform's opener shows it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

type Run = Callable[[list[str]], object]

_STARTFILE: Callable[[str], None] | None = getattr(os, "startfile", None)
"""Windows only."""
_OPENERS = {"darwin": "open"}
_DEFAULT_OPENER = "xdg-open"


def open_in_file_manager(
    folder: Path,
    platform: str = sys.platform,
    startfile: Callable[[str], None] | None = _STARTFILE,
    run: Run | None = subprocess.Popen,
) -> None:
    """Show ``folder`` in the file manager; raises ``OSError`` when it cannot."""
    if platform == "win32":
        assert startfile is not None, "os.startfile exists on Windows"
        startfile(str(folder))
        return
    assert run is not None, "a command runs the platform's opener"
    run([_OPENERS.get(platform, _DEFAULT_OPENER), str(folder)])
