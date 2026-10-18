"""The journal files of past game sessions, as the folder holds them (ADR 0052).

``FolderArchive`` implements the application's ``JournalArchive``: the journal
files of the folder, oldest first, betas left out (ADR 0020), and the entries
of a file whose event is asked for. A player's history can be thousands of
files: a line whose event is not asked for is skipped by its name, before any
JSON decoding. A file whose header tells a beta of the game gives nothing.

It only reads; it never writes in the folder.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator, Sequence
from pathlib import Path

from edrockmaster.application.ports import JournalFile
from edrockmaster.desktop.journal_folder import is_beta_file, journal_files
from edrockmaster.domain.journal_reading import Entry

_EVENT = re.compile(rb'"event"\s*:\s*"([^"]+)"')
_HEADER = "Fileheader"
_BETAS = ("alpha", "beta")


class FolderArchive:
    def __init__(self, directory: Path, logger: logging.Logger) -> None:
        self.directory = directory
        self._logger = logger

    def files(self) -> Sequence[JournalFile]:
        found = []
        for path in journal_files(self.directory):
            if is_beta_file(path):
                continue
            try:
                size = path.stat().st_size
            except OSError as error:
                self._logger.warning("Could not read %s: %s", path, error)
                continue
            found.append(JournalFile(path.name, size))
        return found

    def entries(self, file: JournalFile, events: frozenset[str]) -> Iterator[Entry]:
        wanted = {event.encode() for event in events | {_HEADER}}
        path = self.directory / file.name
        try:
            data = path.read_bytes()
        except OSError as error:
            self._logger.warning("Could not read %s: %s", path, error)
            return
        for line in data.splitlines():
            match = _EVENT.search(line)
            if match is None or match[1] not in wanted:
                continue
            entry = _entry(line)
            if entry is None:
                continue
            if entry["event"] == _HEADER and _is_beta(entry):
                return
            if entry["event"] in events:
                yield entry


def _entry(line: bytes) -> Entry | None:
    try:
        entry = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(entry, dict) or not isinstance(entry.get("event"), str):
        return None
    return entry


def _is_beta(header: Entry) -> bool:
    version = header.get("gameversion")
    return isinstance(version, str) and any(beta in version.lower() for beta in _BETAS)
