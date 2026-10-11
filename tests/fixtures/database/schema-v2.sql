-- Local database of the plugin at schema version 2 (ADR 0018), as released.
-- Kept unchanged: the tests migrate it to the latest version.
PRAGMA user_version = 2;
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
