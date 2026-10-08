-- Local database of the plugin at schema version 1 (ADR 0018), as released.
-- Kept unchanged: the tests migrate it to the latest version.
PRAGMA user_version = 1;
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
