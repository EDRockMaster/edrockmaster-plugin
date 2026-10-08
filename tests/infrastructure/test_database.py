"""The local database on a real SQLite file (ADR 0018)."""

import logging
import re
import sqlite3
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from edrockmaster.infrastructure.database import (
    FILE_NAME,
    DatabaseUnavailableError,
    LocalDatabase,
    WrongThreadError,
)
from edrockmaster.infrastructure.migrations import LATEST_VERSION, MIGRATIONS, Migration

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "database"
NOW = datetime(2026, 10, 8, 14, 30, 5, tzinfo=UTC)
logger = logging.getLogger("test.database")

NOTES = Migration(2, ("CREATE TABLE note (id INTEGER PRIMARY KEY, text TEXT NOT NULL) STRICT",))
BROKEN = Migration(2, ("CREATE TABLE note (id INTEGER PRIMARY KEY)", "SELECT * FROM missing"))


def database(directory: Path, migrations: tuple[Migration, ...] = MIGRATIONS) -> LocalDatabase:
    return LocalDatabase(directory / FILE_NAME, logger, migrations, now=lambda: NOW)


@pytest.fixture
def opened(tmp_path: Path) -> Iterator[LocalDatabase]:
    db = database(tmp_path)
    assert db.open().available
    yield db
    db.close()


def version_of(path: Path) -> int:
    connection = sqlite3.connect(path)
    try:
        [version] = connection.execute("PRAGMA user_version").fetchone()
    finally:
        connection.close()
    return int(version)


def schema_of(connection: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = connection.execute(
        "SELECT name, sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [(name, " ".join(sql.split())) for name, sql in rows]


def fixture_versions() -> list[int]:
    return sorted(
        int(m[1]) for p in FIXTURES.glob("*.sql") if (m := re.match(r"schema-v(\d+)", p.stem))
    )


def load_fixture(version: int, path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript((FIXTURES / f"schema-v{version}.sql").read_text(encoding="utf-8"))
    finally:
        connection.close()


# Opening and migrations


def test_a_new_database_is_created_at_the_latest_version(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db = database(tmp_path / "data")
    with caplog.at_level(logging.INFO):
        opening = db.open()
    assert f"open, schema version {LATEST_VERSION}" in caplog.text
    assert opening.available
    assert opening.moved_aside is None
    assert db.connection().execute("PRAGMA user_version").fetchone() == (LATEST_VERSION,)
    assert db.connection().execute("PRAGMA journal_mode").fetchone() == ("wal",)
    db.close()
    assert (tmp_path / "data" / FILE_NAME).is_file()


def test_migrations_are_numbered_from_one_without_gaps() -> None:
    assert [migration.version for migration in MIGRATIONS] == list(range(1, LATEST_VERSION + 1))


def test_every_schema_version_has_a_fixture() -> None:
    assert fixture_versions() == list(range(1, LATEST_VERSION + 1))


def test_the_latest_fixture_has_the_schema_the_migrations_create(
    tmp_path: Path, opened: LocalDatabase
) -> None:
    load_fixture(LATEST_VERSION, tmp_path / "fixture.sqlite3")
    fixture = sqlite3.connect(tmp_path / "fixture.sqlite3")
    try:
        assert schema_of(fixture) == schema_of(opened.connection())
    finally:
        fixture.close()


@pytest.mark.parametrize("version", fixture_versions())
def test_each_past_version_opens_at_the_latest_and_keeps_its_data(
    tmp_path: Path, version: int
) -> None:
    load_fixture(version, tmp_path / FILE_NAME)
    db = database(tmp_path)
    assert db.open().available
    assert db.connection().execute("PRAGMA user_version").fetchone() == (LATEST_VERSION,)
    assert db.connection().execute("SELECT count(*) FROM engineering_goal").fetchone() == (2,)
    db.close()


def test_a_migration_copies_the_file_first_and_keeps_the_last_copy_only(tmp_path: Path) -> None:
    load_fixture(1, tmp_path / FILE_NAME)
    (tmp_path / f"{FILE_NAME}.v0.bak").write_bytes(b"an older copy")
    db = database(tmp_path, (*MIGRATIONS, NOTES))
    assert db.open().available
    db.connection().execute("INSERT INTO note (text) VALUES ('after')")
    db.close()
    backups = sorted(path.name for path in tmp_path.glob("*.bak"))
    assert backups == [f"{FILE_NAME}.v1.bak"]
    assert version_of(tmp_path / f"{FILE_NAME}.v1.bak") == 1
    assert version_of(tmp_path / FILE_NAME) == 2


def test_no_copy_without_a_migration(tmp_path: Path) -> None:
    for _ in range(2):
        db = database(tmp_path)
        assert db.open().available
        db.close()
    assert not list(tmp_path.glob("*.bak"))


def test_a_failing_migration_is_rolled_back_and_leaves_the_file_unchanged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    load_fixture(1, tmp_path / FILE_NAME)
    db = database(tmp_path, (*MIGRATIONS, BROKEN))
    with caplog.at_level(logging.ERROR):
        opening = db.open()
    assert not opening.available
    assert opening.moved_aside is None
    assert "missing" in caplog.text
    assert not db.is_open
    assert version_of(tmp_path / FILE_NAME) == 1
    connection = sqlite3.connect(tmp_path / FILE_NAME)
    try:
        assert "note" not in {name for name, _ in schema_of(connection)}
    finally:
        connection.close()


# Unreadable files


def test_a_file_that_is_not_a_database_is_moved_aside(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / FILE_NAME).write_bytes(b"this is not a database, " * 100)
    db = database(tmp_path)
    with caplog.at_level(logging.WARNING):
        opening = db.open()
    assert opening.available
    assert opening.moved_aside == tmp_path / f"{FILE_NAME}.unreadable-20261008T143005Z"
    assert opening.moved_aside.read_bytes().startswith(b"this is not a database")
    assert opening.reason is not None
    assert "SQLITE_NOTADB" in opening.reason
    assert "unreadable" in caplog.text
    assert db.connection().execute("PRAGMA user_version").fetchone() == (LATEST_VERSION,)
    db.close()


def test_a_corrupt_database_is_moved_aside(tmp_path: Path) -> None:
    path = tmp_path / FILE_NAME
    load_fixture(1, path)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode = DELETE")
    connection.close()
    data = bytearray(path.read_bytes())
    # Page 2 holds the goals table: overwrite its b-tree header
    page_size = int.from_bytes(data[16:18], "big")
    data[page_size : page_size + 16] = b"\xff" * 16
    path.write_bytes(bytes(data))
    db = database(tmp_path)
    opening = db.open()
    assert opening.available
    assert opening.moved_aside is not None
    db.close()


def test_a_database_of_a_newer_plugin_is_moved_aside(tmp_path: Path) -> None:
    newer = database(tmp_path, (*MIGRATIONS, NOTES))
    assert newer.open().available
    newer.close()
    db = database(tmp_path)
    opening = db.open()
    assert opening.available
    assert opening.reason is not None
    assert "newer version" in opening.reason
    assert opening.moved_aside is not None
    assert version_of(opening.moved_aside) == 2
    assert db.connection().execute("PRAGMA user_version").fetchone() == (LATEST_VERSION,)
    db.close()


def test_moving_aside_never_overwrites_an_earlier_copy(tmp_path: Path) -> None:
    for _ in range(2):
        (tmp_path / FILE_NAME).write_bytes(b"garbage" * 100)
        db = database(tmp_path)
        db.open()
        db.close()
        (tmp_path / FILE_NAME).unlink()
    names = sorted(path.name for path in tmp_path.glob("*.unreadable-*"))
    assert names == [
        f"{FILE_NAME}.unreadable-20261008T143005Z",
        f"{FILE_NAME}.unreadable-20261008T143005Z-2",
    ]


def test_a_database_that_cannot_be_created_is_unavailable(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "data").write_text("a file where the directory should be")
    db = database(tmp_path / "data")
    with caplog.at_level(logging.ERROR):
        opening = db.open()
    assert not opening.available
    assert "unavailable" in caplog.text
    with pytest.raises(DatabaseUnavailableError):
        db.connection()


def test_a_locked_database_is_left_alone(tmp_path: Path) -> None:
    load_fixture(1, tmp_path / FILE_NAME)
    other = sqlite3.connect(tmp_path / FILE_NAME, autocommit=True)
    other.execute("BEGIN EXCLUSIVE")
    db = LocalDatabase(tmp_path / FILE_NAME, logger, (*MIGRATIONS, NOTES), busy_timeout=0)
    try:
        opening = db.open()
    finally:
        other.execute("ROLLBACK")
        other.close()
    assert not opening.available
    assert opening.moved_aside is None
    assert not list(tmp_path.glob("*.unreadable-*"))
    assert version_of(tmp_path / FILE_NAME) == 1


# Threads


def test_only_the_opening_thread_may_use_the_connection(opened: LocalDatabase) -> None:
    assert opened.owner == threading.current_thread().name
    failures: list[BaseException] = []

    def use() -> None:
        try:
            opened.connection()
        except BaseException as error:
            failures.append(error)

    thread = threading.Thread(target=use)
    thread.start()
    thread.join()
    assert len(failures) == 1
    assert isinstance(failures[0], WrongThreadError)


def test_closing_twice_is_harmless(opened: LocalDatabase) -> None:
    opened.close()
    opened.close()
    assert not opened.is_open
    assert opened.owner is None


def test_opening_twice_is_a_mistake(opened: LocalDatabase) -> None:
    with pytest.raises(RuntimeError, match="already open"):
        opened.open()
