"""Write a test fixture back as a game journal file, as the game writes it (ADR 0020).

For the desktop application's smoke test and for trying it by hand:
``EDROCKMASTER_JOURNAL_DIR`` then points to the folder.

Usage: python3 scripts/fixture_to_journal.py <fixture.jsonl> <journal folder>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

JOURNAL_NAME = "Journal.2026-10-08T014139.01.log"


def write(fixture: Path, folder: Path) -> Path:
    lines = fixture.read_text(encoding="utf-8").splitlines()
    entries = [json.dumps(json.loads(line)["entry"], ensure_ascii=False) for line in lines]
    folder.mkdir(parents=True, exist_ok=True)
    journal = folder / JOURNAL_NAME
    journal.write_text("".join(entry + "\r\n" for entry in entries), encoding="utf-8", newline="")
    return journal


def main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    print(write(Path(arguments[0]), Path(arguments[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
