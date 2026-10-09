"""Following the game journal as the game writes it (ADR 0020).

``JournalFollower.poll()`` reads what was added to the journal since the last
call, and hands each entry on. Its first call reads the current file from its
beginning: the application gives the core every entry of the game session, so
that it reaches the same figures as if it had run since the game started. When
the game opens a newer file (a new session, or the next part of a long one), the
follower finishes the current one, then follows the newer from its beginning.

Since the game's 3.3, the journal's ``Cargo`` event lists the ship's cargo only
at load; afterwards the list is in ``Cargo.json``, next to the journal. EDMC
added it to the event, and the core relies on it: so does the follower, when
the file describes that very event (same timestamp), so that a past event read
at start never gets the current cargo.

The game writes whole lines, but a read can still fall in the middle of one: an
incomplete line waits for the rest. A line that is not a journal entry is
logged and skipped. The follower only reads; it never writes in the folder.

``JournalWatcher`` calls ``poll()`` on a thread of its own, every second.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from pathlib import Path

from edrockmaster.desktop.journal_folder import is_beta_file, journal_files
from edrockmaster.domain.journal_reading import Entry

type OnEntry = Callable[[Entry, bool], None]
"""Receives each entry, and whether it comes from a beta of the game."""

POLL_SECONDS = 1.0
"""As often as EDMC polled a running game: reading a few new lines costs nothing."""

_VERSION_EVENTS = frozenset({"Fileheader", "LoadGame"})
CARGO_FILE = "Cargo.json"


class JournalFollower:
    def __init__(self, directory: Path, on_entry: OnEntry, logger: logging.Logger) -> None:
        self.directory = directory
        self._on_entry = on_entry
        self._logger = logger
        self._file: Path | None = None
        self._offset = 0
        self._pending = b""
        self._beta = False
        self._missing_logged = False

    @property
    def current_file(self) -> Path | None:
        return self._file

    def poll(self) -> int:
        """Read what is new in the journal; return how many entries were handed on."""
        files = journal_files(self.directory)
        if not files:
            if not self._missing_logged:
                self._logger.warning("No journal file in %s yet", self.directory)
                self._missing_logged = True
            return 0
        self._missing_logged = False
        read = 0
        if self._file is None or self._file not in files:
            # At start, or the current file was moved away: the newest, from its beginning
            self._open(files[-1])
        else:
            # Newer files: finish the current one, then go through each in order
            for newer in files[files.index(self._file) + 1 :]:
                read += self._read()
                self._open(newer)
        return read + self._read()

    def _open(self, path: Path) -> None:
        if self._file is not None:
            self._logger.info("New journal file %s, after %s", path.name, self._file.name)
        else:
            self._logger.info("Reading the journal from %s", path.name)
        self._file, self._offset, self._pending = path, 0, b""
        self._beta = is_beta_file(path)

    def _read(self) -> int:
        assert self._file is not None, "poll() opens a file before reading"
        try:
            with self._file.open("rb") as handle:
                handle.seek(self._offset)
                data = handle.read()
        except OSError as error:
            self._logger.warning("Could not read %s: %s", self._file, error)
            return 0
        self._offset += len(data)
        *lines, self._pending = (self._pending + data).split(b"\n")
        handed = 0
        for line in lines:
            entry = self._entry(line)
            if entry is not None:
                self._note_version(entry)
                self._on_entry(self._with_cargo(entry), self._beta)
                handed += 1
        return handed

    def _entry(self, line: bytes) -> Entry | None:
        text = line.strip()
        if not text:
            return None
        try:
            entry = json.loads(text.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._logger.warning("Not a journal entry in %s: %r", self._file, text[:200])
            return None
        if not isinstance(entry, dict) or not isinstance(entry.get("event"), str):
            self._logger.warning("Not a journal entry in %s: %r", self._file, text[:200])
            return None
        return entry

    def _with_cargo(self, entry: Entry) -> Entry:
        """The ship's ``Cargo`` event with its list, from ``Cargo.json`` when it describes it."""
        if entry["event"] != "Cargo" or entry.get("Vessel") != "Ship" or "Inventory" in entry:
            return entry
        try:
            cargo = json.loads((self.directory / CARGO_FILE).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return entry
        if (
            not isinstance(cargo, dict)
            or cargo.get("timestamp") != entry.get("timestamp")
            or cargo.get("Vessel") != "Ship"
            or not isinstance(cargo.get("Inventory"), list)
        ):
            return entry
        return {**entry, "Inventory": cargo["Inventory"]}

    def _note_version(self, entry: Entry) -> None:
        """A beta of the game says so in its version, as EDMC read it."""
        if entry["event"] in _VERSION_EVENTS:
            version = entry.get("gameversion")
            if isinstance(version, str) and self._file is not None:
                lowered = version.lower()
                self._beta = is_beta_file(self._file) or "alpha" in lowered or "beta" in lowered


class JournalWatcher:
    """Polls a ``JournalFollower`` on its own thread until stopped."""

    def __init__(
        self, follower: JournalFollower, logger: logging.Logger, interval: float = POLL_SECONDS
    ) -> None:
        self._follower = follower
        self._logger = logger
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("the journal watcher can only be started once")
        self._thread = threading.Thread(target=self._run, name="EDRockMaster journal", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> bool:
        """Stop polling; return whether the thread has ended."""
        self._stop.set()
        if self._thread is None:
            return True
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._follower.poll()
            except Exception:
                self._logger.exception("Reading the journal failed")
            self._stop.wait(self._interval)
