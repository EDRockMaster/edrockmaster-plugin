"""One running application per user: a lock on a file of the data directory.

The operating system holds the lock for the process, and drops it when the process ends,
even if it crashes: no stale lock to clean up. The lock is taken before the database, the
local server and the journal are touched.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import TracebackType
from typing import IO

LOCK_NAME = "instance.lock"


class InstanceLock:
    """``acquire`` gives ``False`` if another process holds the lock; ``release`` frees it."""

    def __init__(self, directory: Path, platform: str = sys.platform) -> None:
        self._path = directory / LOCK_NAME
        self._platform = platform
        self._file: IO[bytes] | None = None

    def acquire(self) -> bool:
        if self._file is not None:
            return True
        self._path.parent.mkdir(parents=True, exist_ok=True)
        file = self._path.open("ab+")
        if not self._lock(file):
            file.close()
            return False
        self._file = file
        return True

    def release(self) -> None:
        if self._file is None:
            return
        file, self._file = self._file, None
        try:
            self._unlock(file)
        finally:
            file.close()

    def __enter__(self) -> InstanceLock:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.release()

    def _lock(self, file: IO[bytes]) -> bool:
        try:
            if self._platform == "win32":
                import msvcrt  # noqa: PLC0415 - Windows only

                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
            else:
                import fcntl  # noqa: PLC0415 - not on Windows

                fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def _unlock(self, file: IO[bytes]) -> None:
        if self._platform == "win32":
            import msvcrt  # noqa: PLC0415 - Windows only

            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
        else:
            import fcntl  # noqa: PLC0415 - not on Windows

            fcntl.flock(file.fileno(), fcntl.LOCK_UN)
