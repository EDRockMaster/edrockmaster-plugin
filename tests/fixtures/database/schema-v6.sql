-- Local database of the plugin at schema version 6 (ADR 0018), as released.
-- Kept unchanged: the tests migrate it to the latest version.
PRAGMA user_version = 6;
CREATE TABLE engineering_goal (
    id TEXT PRIMARY KEY,
    position INTEGER NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK (kind IN ('blueprint', 'experimental_effect')),
    name TEXT NOT NULL CHECK (name <> ''),
    module TEXT NOT NULL CHECK (module <> ''),
    grade INTEGER CHECK (grade BETWEEN 1 AND 5),
    count INTEGER NOT NULL CHECK (count >= 1),
    CHECK ((kind = 'blueprint') = (grade IS NOT NULL))
) STRICT;
INSERT INTO engineering_goal VALUES ('5b0f6c1d', 1, 'blueprint', 'FSD_LongRange', 'fsd', 5, 3);
INSERT INTO engineering_goal VALUES ('9e2a7d4c', 2, 'experimental_effect', 'special_fsd_heavy', 'fsd', NULL, 1);
CREATE TABLE class_upgrade_goal (
    id TEXT PRIMARY KEY,
    position INTEGER NOT NULL UNIQUE,
    item TEXT NOT NULL CHECK (item <> ''),
    from_class INTEGER NOT NULL CHECK (from_class BETWEEN 1 AND 4),
    to_class INTEGER NOT NULL CHECK (to_class BETWEEN 2 AND 5),
    set_at TEXT NOT NULL CHECK (set_at <> ''),
    equipment_id INTEGER,
    CHECK (from_class < to_class)
) STRICT;
INSERT INTO class_upgrade_goal VALUES ('7c3e1a9b', 1, 'tacticalsuit', 1, 4, '2026-10-11T01:30:15+00:00', 1878707285049801);
CREATE TABLE modification_goal (
    id TEXT PRIMARY KEY,
    position INTEGER NOT NULL UNIQUE,
    item TEXT NOT NULL CHECK (item <> ''),
    modification TEXT NOT NULL CHECK (modification <> ''),
    set_at TEXT NOT NULL CHECK (set_at <> ''),
    equipment_id INTEGER
) STRICT;
INSERT INTO modification_goal VALUES ('2d8f5e0a', 1, 'utilitysuit', 'suit_backpackcapacity', '2026-10-11T03:40:00+00:00', NULL);
CREATE TABLE engineer_unlock_goal (
    id TEXT PRIMARY KEY,
    position INTEGER NOT NULL UNIQUE,
    engineer_id INTEGER NOT NULL CHECK (engineer_id > 0)
) STRICT;
INSERT INTO engineer_unlock_goal VALUES ('6a1c9e3f', 1, 400004);
CREATE TABLE goal_priority (
    goal_id TEXT PRIMARY KEY,
    rank INTEGER NOT NULL UNIQUE
) STRICT;
INSERT INTO goal_priority VALUES ('6a1c9e3f', 1);
INSERT INTO goal_priority VALUES ('5b0f6c1d', 2);
INSERT INTO goal_priority VALUES ('7c3e1a9b', 3);
INSERT INTO goal_priority VALUES ('9e2a7d4c', 4);
INSERT INTO goal_priority VALUES ('2d8f5e0a', 5);
CREATE TABLE source_cache (
    source TEXT NOT NULL CHECK (source <> ''),
    request TEXT NOT NULL CHECK (request <> ''),
    read_at TEXT NOT NULL CHECK (read_at <> ''),
    answer TEXT NOT NULL,
    PRIMARY KEY (source, request)
) STRICT;
INSERT INTO source_cache VALUES ('ardent', 'https://api.ardent-insight.com/v2/system/name/Borann/commodity/name/painite/nearby/imports', '2026-10-11T21:40:00+00:00', '[]');
