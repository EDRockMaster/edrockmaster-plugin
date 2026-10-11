"""Translation of raw journal entries into facts of the community goals context.

The context's anti-corruption layer for the game journal (ADR 0032), built on
the tolerant helpers of the shared kernel (``journal_reading``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from edrockmaster.domain.journal_reading import (
    Entry,
    Parser,
    instant,
    items,
    optional,
    required,
    translate,
)


@dataclass(frozen=True, slots=True)
class CommunityGoal:
    cgid: int
    title: str
    system: str | None
    expiry: datetime | None
    complete: bool
    contribution: int
    """The commander's contribution, a bare number: credits, tons or else, depending on the goal."""
    percentile_band: int | None
    tier_reached: str | None
    top_tier: str | None


@dataclass(frozen=True, slots=True)
class CommunityGoalsUpdated:
    """The community goals the commander has joined, as the game reports them."""

    at: datetime
    goals: tuple[CommunityGoal, ...]


@dataclass(frozen=True, slots=True)
class CommunityGoalLeft:
    """The commander collected a community goal's reward, or discarded the goal."""

    at: datetime
    cgid: int


type Fact = CommunityGoalsUpdated | CommunityGoalLeft


def parse_entry(entry: Entry) -> Fact | None:
    """Return the community goals fact carried by a journal entry, or ``None`` if irrelevant."""
    return translate(entry, _PARSERS)


def _goal(item: Entry) -> CommunityGoal:
    top_tier = item.get("TopTier")
    return CommunityGoal(
        cgid=required(item, "CGID", int),
        title=required(item, "Title", str),
        system=optional(item, "SystemName", str),
        expiry=instant(item, "Expiry") if "Expiry" in item else None,
        complete=bool(optional(item, "IsComplete", bool)),
        contribution=optional(item, "PlayerContribution", int) or 0,
        percentile_band=optional(item, "PlayerPercentileBand", int),
        tier_reached=optional(item, "TierReached", str),
        top_tier=optional(top_tier, "Name", str) if isinstance(top_tier, dict) else None,
    )


def _goals(entry: Entry, at: datetime) -> CommunityGoalsUpdated:
    return CommunityGoalsUpdated(
        at=at, goals=tuple(_goal(item) for item in items(entry, "CurrentGoals"))
    )


def _goal_left(entry: Entry, at: datetime) -> CommunityGoalLeft:
    return CommunityGoalLeft(at, cgid=required(entry, "CGID", int))


_PARSERS: dict[str, Parser[Fact | None]] = {
    "CommunityGoal": _goals,
    "CommunityGoalReward": _goal_left,
    "CommunityGoalDiscard": _goal_left,
}
