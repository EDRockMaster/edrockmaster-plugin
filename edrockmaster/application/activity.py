"""The activities the application assists, each one a bounded context (ADR 0011)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Activity(Enum):
    MINING = "mining"
    COMBAT = "combat"
    TRADE = "trade"
    ENGINEERING = "engineering"
    COMMUNITY_GOALS = "communityGoals"
    """Not a session: the goals joined (ADR 0032)."""


@dataclass(frozen=True, slots=True)
class EndedSessionsForgotten:
    """The sessions ended so far belong to a past game: the live view no longer shows them.

    Told when a game is loaded, and when the game closed before the application started
    (the newest journal file, read again at start, is a past game's).
    """
