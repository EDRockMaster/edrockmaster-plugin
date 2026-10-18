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
    Migration(
        3,
        (
            # Modifications of suits and weapons (ADR 0027): an item type, or the player's own
            # item, and the modification by its journal symbol
            """
            CREATE TABLE modification_goal (
                id TEXT PRIMARY KEY,
                position INTEGER NOT NULL UNIQUE,
                item TEXT NOT NULL CHECK (item <> ''),
                modification TEXT NOT NULL CHECK (modification <> ''),
                set_at TEXT NOT NULL CHECK (set_at <> ''),
                equipment_id INTEGER
            ) STRICT
            """,
        ),
    ),
    Migration(
        4,
        (
            # Engineer unlocks (ADR 0027, ADR 0031): the engineer, by the id the journal gives
            """
            CREATE TABLE engineer_unlock_goal (
                id TEXT PRIMARY KEY,
                position INTEGER NOT NULL UNIQUE,
                engineer_id INTEGER NOT NULL CHECK (engineer_id > 0)
            ) STRICT
            """,
        ),
    ),
    Migration(
        5,
        (
            # The player's priority over all the goals, whatever their kind (ADR 0033): the
            # goals stored keep the order they were read in, ship goals first
            """
            CREATE TABLE goal_priority (
                goal_id TEXT PRIMARY KEY,
                rank INTEGER NOT NULL UNIQUE
            ) STRICT
            """,
            """
            INSERT INTO goal_priority (goal_id, rank)
            SELECT id, row_number() OVER (ORDER BY kind, position) FROM (
                SELECT id, 1 AS kind, position FROM engineering_goal
                UNION ALL SELECT id, 2, position FROM class_upgrade_goal
                UNION ALL SELECT id, 3, position FROM modification_goal
                UNION ALL SELECT id, 4, position FROM engineer_unlock_goal
            )
            """,
        ),
    ),
    Migration(
        6,
        (
            # Answers of the community sources (ADR 0039): what a source published, never the
            # player's data; the request identifies the answer, read_at in UTC, ISO 8601
            """
            CREATE TABLE source_cache (
                source TEXT NOT NULL CHECK (source <> ''),
                request TEXT NOT NULL CHECK (request <> ''),
                read_at TEXT NOT NULL CHECK (read_at <> ''),
                answer TEXT NOT NULL,
                PRIMARY KEY (source, request)
            ) STRICT
            """,
        ),
    ),
    Migration(
        7,
        (
            # The journal files of past game sessions read and counted (ADR 0052), with the
            # commander playing at their end; read_at in UTC, ISO 8601
            """
            CREATE TABLE journal_file_read (
                name TEXT PRIMARY KEY CHECK (name <> ''),
                size INTEGER NOT NULL CHECK (size >= 0),
                commander TEXT NOT NULL,
                galaxy TEXT NOT NULL CHECK (galaxy IN ('live', 'legacy')),
                read_at TEXT NOT NULL CHECK (read_at <> '')
            ) STRICT
            """,
            # The version of the rules that read them, and who played at the end of the last one
            """
            CREATE TABLE past_journals (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL CHECK (version >= 1),
                commander TEXT NOT NULL,
                galaxy TEXT NOT NULL CHECK (galaxy IN ('live', 'legacy'))
            ) STRICT
            """,
            # What they gave: the vouchers each commander holds, per kind and paying faction,
            # since the oldest of them (UTC, ISO 8601)
            """
            CREATE TABLE unredeemed_voucher (
                commander TEXT NOT NULL,
                galaxy TEXT NOT NULL CHECK (galaxy IN ('live', 'legacy')),
                kind TEXT NOT NULL CHECK (kind IN ('bounty', 'combat_bond')),
                faction TEXT NOT NULL,
                amount INTEGER NOT NULL CHECK (amount > 0),
                since TEXT NOT NULL CHECK (since <> ''),
                PRIMARY KEY (commander, galaxy, kind, faction)
            ) STRICT
            """,
        ),
    ),
)
