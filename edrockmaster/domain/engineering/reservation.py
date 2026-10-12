"""The goals' priority (ADR 0033): the materials held go to the goals in the player's order.

The ship's materials and the on-foot ones are reserved apart. Each goal takes what it needs
of what is left, even when it cannot be completed, so that a goal is **ready** only when
nothing is missing once the goals above it have taken their share; one ready **alone** but
not after them says so. A goal that does not count materials (its inventory unknown, its
recipe unknown, or what is left to do not only materials) takes none.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace

from edrockmaster.domain.engineering.goals import BlueprintGoal, ExperimentalEffectGoal
from edrockmaster.domain.engineering.progress import GoalProgress, missing


def reserve(
    alone: Iterable[GoalProgress], ship: Mapping[str, int], on_foot: Mapping[str, int]
) -> tuple[GoalProgress, ...]:
    """Each goal's progress, in the priority, once the goals above it took their share.

    ``alone``: each goal's progress as if it were the only one, in the player's order.
    """
    left_ship, left_on_foot = dict(ship), dict(on_foot)
    reserved = []
    for progress in alone:
        if progress.missing is None or not progress.known or not progress.counted:
            reserved.append(progress)  # nothing it can count: it takes nothing
            continue
        goal = progress.goal
        left = (
            left_ship if isinstance(goal, BlueprintGoal | ExperimentalEffectGoal) else left_on_foot
        )
        lacking = missing(progress.needed, left)
        for symbol, count in progress.needed.items():
            left[symbol] = max(0, left.get(symbol, 0) - count)
        reserved.append(replace(progress, missing=lacking, ready_alone=progress.ready))
    return tuple(reserved)
