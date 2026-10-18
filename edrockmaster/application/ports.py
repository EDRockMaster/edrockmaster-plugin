"""Ports of the application layer, implemented by adapters in ``infrastructure``."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from edrockmaster.application.community import Answer
from edrockmaster.application.settings import PluginSettings
from edrockmaster.domain.combat.vouchers import CommanderKey, VoucherLedger
from edrockmaster.domain.engineering.goals import Goal, GoalId
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.mining.hotspots import HotspotPage, HotspotQuery
from edrockmaster.domain.mining.limpets import LimpetAlertRaised
from edrockmaster.domain.mining.markets import MarketOffer, SaleQuery
from edrockmaster.domain.mining.prospecting import ProspectorAlertRaised
from edrockmaster.domain.situation.route import RouteAlertRaised


class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current time, timezone-aware (UTC)."""
        ...


class SettingsStore(Protocol):
    def load(self) -> PluginSettings:
        """Return the stored settings, or the defaults for anything missing or invalid."""
        ...

    def save(self, settings: PluginSettings) -> None: ...


class Notifier(Protocol):
    def notify(self, alert: ProspectorAlertRaised | LimpetAlertRaised | RouteAlertRaised) -> None:
        """Draw the player's attention to an alert (sound). Must not block."""
        ...


class JournalRecorder(Protocol):
    def record(self, entry: Entry, is_beta: bool) -> None:
        """Keep a verbatim copy of a journal entry. Must not block."""
        ...


class GoalRepository(Protocol):
    """The player's engineering goals, kept across restarts (ADR 0017, ADR 0018).

    No method blocks: the storage works on the I/O thread. The goals are listed
    in the player's order, their priority (ADR 0033); a new goal comes last.
    """

    def load(self, on_loaded: Callable[[tuple[Goal, ...]], None]) -> None:
        """Read the stored goals; ``on_loaded`` is called later, on the main thread."""
        ...

    def add(self, goal: Goal) -> None: ...

    def replace(self, goal: Goal) -> None:
        """Store a changed goal (its rolls or applications), keeping its place."""
        ...

    def remove(self, goal_id: GoalId) -> None: ...

    def reorder(self, order: Sequence[GoalId]) -> None:
        """Store the player's priority (ADR 0033): every goal, first to last."""
        ...


class GalaxyCatalogue(Protocol):
    """Systems, bodies and rings as a community source knows them (ADR 0039, ADR 0040).

    No method blocks: the source is asked on the I/O thread, and the answer is
    handed to the callback later, on the core thread.
    """

    def find_hotspots(
        self,
        query: HotspotQuery,
        on_answer: Callable[[Answer[HotspotPage]], None],
        *,
        refresh: bool = False,
    ) -> None:
        """Rings with the query's hotspots, nearest first; ``refresh`` skips the cache."""
        ...


class CommodityMarkets(Protocol):
    """Markets as a community source knows them (ADR 0039, ADR 0040); does not block."""

    def find_buyers(
        self,
        query: SaleQuery,
        on_answer: Callable[[Answer[tuple[MarketOffer, ...]]], None],
        *,
        refresh: bool = False,
    ) -> None:
        """Markets that buy the commodity around the system, as the source gives them."""
        ...


@dataclass(frozen=True, slots=True)
class JournalFile:
    """A journal file of the game (ADR 0052), by name; its size tells whether it changed."""

    name: str
    size: int


@dataclass(frozen=True, slots=True)
class IndexedFile:
    """A journal file read and counted, with the commander playing at its end."""

    file: JournalFile
    commander: CommanderKey


@dataclass(slots=True)
class KeptHistory:
    """What the journals of past game sessions gave, as kept (ADR 0052)."""

    files: dict[str, IndexedFile] = field(default_factory=dict)
    """The files read and counted, by name, those since removed from the folder included."""
    ledger: VoucherLedger = field(default_factory=VoucherLedger)


class JournalArchive(Protocol):
    """The journal files in the folder; blocks (ADR 0052)."""

    def files(self) -> Sequence[JournalFile]:
        """Every journal file of the game but its betas, oldest first."""
        ...

    def entries(self, file: JournalFile, events: frozenset[str]) -> Iterable[Entry]:
        """The entries of a file whose event is one of ``events``, in order."""
        ...


class PastJournalStore(Protocol):
    """The index of the journal files read, and what they gave; blocks (ADR 0052).

    ``version`` is the version of the rules that read the journal: a store kept
    under another version is empty, so that every file is read again.
    """

    def load(self, version: int) -> KeptHistory: ...

    def save(self, version: int, indexed: IndexedFile, ledger: VoucherLedger) -> None:
        """Index a file and keep the ledger it led to, together or not at all."""
        ...

    def clear(self, version: int) -> None:
        """Forget every file read and what they gave."""
        ...
