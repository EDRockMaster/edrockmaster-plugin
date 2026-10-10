"""The application's local database: one SQLite file in the data directory (ADR 0018).

Only the I/O thread uses it: ``open()`` runs there, and ``connection()`` refuses
any other thread. The schema is versioned with ``PRAGMA user_version`` and
migrated at opening (``migrations.py``); before a migration, the file is copied
to ``edrockmaster.sqlite3.v<N>.bak``, and only the last copy is kept.

A file the application cannot read, because it is corrupt or written by a
newer version, is moved aside as ``edrockmaster.sqlite3.unreadable-<date>`` and a
new one is created. Any other failure (the file is locked by another instance,
the disk refuses it, a migration fails) leaves the file as it is, and the
database is unavailable until the application restarts. The application never
fails because of it.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from edrockmaster.infrastructure.migrations import MIGRATIONS, Migration

FILE_NAME = "edrockmaster.sqlite3"

BUSY_TIMEOUT = 5.0
"""Seconds; how long a statement waits for another connection (another instance) before failing."""

_UNREADABLE_ERRORS = frozenset({"SQLITE_CORRUPT", "SQLITE_NOTADB"})


class DatabaseUnavailableError(RuntimeError):
    """The database is not open: not yet, closed, or it could not be opened."""


class WrongThreadError(RuntimeError):
    """The database is used outside the thread that opened it (ADR 0018)."""


class _UnreadableError(Exception):
    """The file must be moved aside: the application cannot read it."""


@dataclass(frozen=True, slots=True)
class Opening:
    """What happened when the database was opened."""

    available: bool
    moved_aside: Path | None = None
    """Where the unreadable file went, if it was moved aside."""
    reason: str | None = None
    """Why the file was moved aside, or why the database is unavailable."""


def _now() -> datetime:
    return datetime.now(UTC)


class LocalDatabase:
    def __init__(
        self,
        path: Path,
        logger: logging.Logger,
        migrations: Sequence[Migration] = MIGRATIONS,
        now: Callable[[], datetime] = _now,
        busy_timeout: float = BUSY_TIMEOUT,
    ) -> None:
        self.path = path
        self._busy_timeout = busy_timeout
        self._logger = logger
        self._migrations = tuple(migrations)
        self._now = now
        self._connection: sqlite3.Connection | None = None
        self._owner: threading.Thread | None = None

    @property
    def latest_version(self) -> int:
        return self._migrations[-1].version if self._migrations else 0

    @property
    def owner(self) -> str | None:
        """Name of the thread that opened the database, the only one allowed to use it."""
        return self._owner.name if self._owner is not None else None

    @property
    def is_open(self) -> bool:
        return self._connection is not None

    def connection(self) -> sqlite3.Connection:
        """The open connection, for the thread that opened it only."""
        if self._connection is None:
            raise DatabaseUnavailableError(f"the local database {self.path} is not open")
        if threading.current_thread() is not self._owner:
            raise WrongThreadError(
                f"the local database is used by {threading.current_thread().name!r}, "
                f"it belongs to {self.owner!r}"
            )
        return self._connection

    def open(self) -> Opening:
        """Open the file, migrate it, or replace it if unreadable. Never raises."""
        if self._connection is not None:
            raise RuntimeError("the local database is already open")
        try:
            return self._open()
        except _UnreadableError as unreadable:
            reason = str(unreadable)
        except (sqlite3.Error, OSError) as error:
            return self._unavailable(error)
        try:
            moved = self._move_aside()
        except OSError as error:
            return self._unavailable(error)
        self._logger.warning(
            "Local database %s unreadable (%s): moved aside to %s, a new one is created",
            self.path,
            reason,
            moved,
        )
        try:
            self._open()
        except (_UnreadableError, sqlite3.Error, OSError) as error:
            return self._unavailable(error, moved)
        return Opening(available=True, moved_aside=moved, reason=reason)

    def close(self) -> None:
        if self._connection is None:
            return
        self.connection().close()
        self._connection = None
        self._owner = None

    def _open(self) -> Opening:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, autocommit=True, timeout=self._busy_timeout)
        try:
            self._prepare(connection)
            version = self._migrate(connection, self._check(connection))
        except BaseException:
            connection.close()
            raise
        self._connection = connection
        self._owner = threading.current_thread()
        self._logger.info("Local database %s open, schema version %d", self.path, version)
        return Opening(available=True)

    def _prepare(self, connection: sqlite3.Connection) -> None:
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA foreign_keys = ON")
            [result] = connection.execute("PRAGMA quick_check(1)").fetchone()
        except sqlite3.DatabaseError as error:
            if error.sqlite_errorname in _UNREADABLE_ERRORS:
                raise _UnreadableError(f"{error.sqlite_errorname}: {error}") from error
            raise
        if result != "ok":
            raise _UnreadableError(f"integrity check failed: {result}")

    def _check(self, connection: sqlite3.Connection) -> int:
        [version] = connection.execute("PRAGMA user_version").fetchone()
        if version > self.latest_version:
            raise _UnreadableError(
                f"schema version {version}, written by a newer version of the application "
                f"(this one knows up to {self.latest_version})"
            )
        return int(version)

    def _migrate(self, connection: sqlite3.Connection, version: int) -> int:
        """Apply the pending migrations; return the schema version reached."""
        pending = [migration for migration in self._migrations if migration.version > version]
        if not pending:
            return version
        if version > 0:
            self._back_up(connection, version)
        for migration in pending:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for statement in migration.statements:
                    connection.execute(statement)
                connection.execute(f"PRAGMA user_version = {migration.version:d}")
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            connection.execute("COMMIT")
            self._logger.info("Local database migrated to schema version %d", migration.version)
        return pending[-1].version

    def _back_up(self, connection: sqlite3.Connection, version: int) -> None:
        backup = self.path.with_name(f"{self.path.name}.v{version}.bak")
        partial = backup.with_name(backup.name + ".partial")
        partial.unlink(missing_ok=True)
        target = sqlite3.connect(partial)
        try:
            connection.backup(target)
        finally:
            target.close()
        partial.replace(backup)
        for older in self.path.parent.glob(f"{self.path.name}.v*.bak"):
            if older != backup:
                older.unlink()

    def _move_aside(self) -> Path | None:
        if not self.path.exists():
            return None
        stamp = f"{self._now().astimezone(UTC):%Y%m%dT%H%M%SZ}"
        aside = self.path.with_name(f"{self.path.name}.unreadable-{stamp}")
        attempt = 1
        while aside.exists():
            attempt += 1
            aside = self.path.with_name(f"{self.path.name}.unreadable-{stamp}-{attempt}")
        # Its -wal and -shm files are gone: SQLite removes them when the last connection closes
        self.path.replace(aside)
        return aside

    def _unavailable(self, error: BaseException, moved: Path | None = None) -> Opening:
        self._logger.error(
            "Local database %s unavailable until the application restarts: %s",
            self.path,
            error,
            exc_info=error,
        )
        return Opening(available=False, moved_aside=moved, reason=str(error))
