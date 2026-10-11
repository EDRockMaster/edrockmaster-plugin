"""Schema of the application's local database (ADR 0018), one migration per version.

Migrations are applied in order, forward only, each in its own transaction. A
migration, once released, never changes: a change is a new migration. Every
version has a fixture in ``tests/fixtures/database/``, opened by the tests.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    """The schema version (``PRAGMA user_version``) once applied."""
    statements: tuple[str, ...]


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        1,
        (
            # Engineering goals (ADR 0017): a blueprint at a grade, or an experimental effect
            """
            CREATE TABLE engineering_goal (
                id TEXT PRIMARY KEY,
                position INTEGER NOT NULL UNIQUE,
                kind TEXT NOT NULL CHECK (kind IN ('blueprint', 'experimental_effect')),
                name TEXT NOT NULL CHECK (name <> ''),
                module TEXT NOT NULL CHECK (module <> ''),
                grade INTEGER CHECK (grade BETWEEN 1 AND 5),
                count INTEGER NOT NULL CHECK (count >= 1),
                CHECK ((kind = 'blueprint') = (grade IS NOT NULL))
            ) STRICT
            """,
        ),
    ),
    Migration(
        2,
        (
            # Class upgrades of suits and weapons (ADR 0027): kept apart from the ship goals,
            # whose kinds the first table checks; the time it was set in UTC, ISO 8601
            """
            CREATE TABLE class_upgrade_goal (
                id TEXT PRIMARY KEY,
                position INTEGER NOT NULL UNIQUE,
                item TEXT NOT NULL CHECK (item <> ''),
                from_class INTEGER NOT NULL CHECK (from_class BETWEEN 1 AND 4),
                to_class INTEGER NOT NULL CHECK (to_class BETWEEN 2 AND 5),
                set_at TEXT NOT NULL CHECK (set_at <> ''),
                equipment_id INTEGER,
                CHECK (from_class < to_class)
            ) STRICT
            """,
        ),
    ),
)

LATEST_VERSION = MIGRATIONS[-1].version
