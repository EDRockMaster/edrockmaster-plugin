"""The collection of materials (ADR 0017): what a play session gained, used and capped.

A collection runs from the first change of materials to game close or reset; death does
not end it (materials survive it). It counts what was gained per category and what was
used, the materials that reached their cap, and on foot (ADR 0027) the player's own
materials brought into the backpack, by kind, and what the backpack carried at a death.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from edrockmaster.domain.engineering.catalogue import MaterialCategory, OnFootKind
from edrockmaster.domain.engineering.journal import ChangeCause, MaterialChange

_GAINS = frozenset({ChangeCause.COLLECTED, ChangeCause.REWARDED})
"""Changes that bring new materials in; a trade only converts them."""


class CollectionEndReason(Enum):
    GAME_CLOSED = "game_closed"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class CollectionStats:
    started_at: datetime
    gained: Mapping[MaterialCategory | None, int]
    """Materials collected or rewarded, by category (``None``: not in the catalogue)."""
    used: int
    """Materials spent: rolls, effects, synthesis, brokers, contributions, research."""
    capped: tuple[str, ...]
    """Materials that reached their cap during the collection, in that order."""
    gained_on_foot: Mapping[OnFootKind, int] = field(default_factory=dict)
    """The player's own on-foot materials brought into the backpack, by kind."""
    lost_on_foot: int = 0
    """The player's own on-foot materials the backpack carried at a death."""


@dataclass(slots=True)
class Collection:
    """A running collection. Mutated only through ``EngineeringTracker``."""

    started_at: datetime
    gained: Counter[MaterialCategory | None] = field(default_factory=Counter)
    used: int = 0
    capped: list[str] = field(default_factory=list)
    gained_on_foot: Counter[OnFootKind] = field(default_factory=Counter)
    lost_on_foot: int = 0

    def count(
        self,
        cause: ChangeCause,
        changes: Iterable[MaterialChange],
        category_of: Callable[[str], MaterialCategory | None],
    ) -> None:
        """Count changes of ship materials: gains by category, uses; a trade is neither."""
        for change in changes:
            if change.count > 0 and cause in _GAINS:
                self.gained[category_of(change.symbol)] += change.count
            elif change.count < 0 and cause is not ChangeCause.TRADED:
                self.used -= change.count

    def cap(self, symbols: Iterable[str]) -> None:
        for symbol in symbols:
            if symbol not in self.capped:
                self.capped.append(symbol)

    def stats(self) -> CollectionStats:
        return CollectionStats(
            self.started_at,
            dict(self.gained),
            self.used,
            tuple(self.capped),
            dict(self.gained_on_foot),
            self.lost_on_foot,
        )
