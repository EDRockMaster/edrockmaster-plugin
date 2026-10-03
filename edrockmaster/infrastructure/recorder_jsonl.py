"""Journal recorder: verbatim copies of journal entries, as JSON lines.

Recordings become test fixtures (``tests/fixtures/``) and replays.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from edrockmaster.domain.journal import Entry
from edrockmaster.infrastructure.worker import Job


class JsonlJournalRecorder:
    """One file per EDMC run; each line is ``{"is_beta": …, "entry": {…}}``."""

    def __init__(
        self, directory: Path, submit: Callable[[Job], None], started_at: datetime
    ) -> None:
        self._submit = submit
        self.path = directory / f"journal-{started_at.astimezone(UTC):%Y%m%dT%H%M%SZ}.jsonl"

    def record(self, entry: Entry, is_beta: bool) -> None:
        # Serialise now: EDMC hands the same dict to every plugin, it may change later
        line = json.dumps({"is_beta": is_beta, "entry": entry}, ensure_ascii=False, default=str)
        self._submit(lambda: self._append(line))

    def _append(self, line: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as file:
            file.write(line + "\n")
