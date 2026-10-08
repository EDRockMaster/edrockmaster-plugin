"""Goals: what the player aims at in engineering (ADR 0017).

A goal is a **blueprint** at a grade, with the number of **rolls** the player
expects to need, or an **experimental effect**, with a number of
**applications**. The game does not tell how many rolls a grade takes (it
depends on the engineer's rank and on luck): the player sets it, one by default.

A goal names its blueprint or effect by its journal name, and the module it is
for by the catalogue's module key: the engineers offering a grade depend on the
module. Goals are the player's own and are stored (ADR 0018); their identity
is chosen when they are made, so that they can be stored without waiting for
the storage.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

MAX_GRADE = 5


@dataclass(frozen=True, slots=True)
class GoalId:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("a goal id cannot be empty")

    @classmethod
    def new(cls) -> GoalId:
        return cls(uuid.uuid4().hex)


def _require_name(value: str, what: str) -> None:
    if not value.strip():
        raise ValueError(f"a goal needs the name of its {what}")


@dataclass(frozen=True, slots=True)
class BlueprintGoal:
    id: GoalId
    blueprint: str
    """Journal name of the blueprint, as in ``EngineerCraft`` (``FSD_LongRange``)."""
    module: str
    grade: int
    rolls: int = 1

    def __post_init__(self) -> None:
        _require_name(self.blueprint, "blueprint")
        _require_name(self.module, "module")
        if not 1 <= self.grade <= MAX_GRADE:
            raise ValueError(f"a grade is from 1 to {MAX_GRADE}, not {self.grade}")
        if self.rolls < 1:
            raise ValueError(f"a goal takes at least one roll, not {self.rolls}")


@dataclass(frozen=True, slots=True)
class ExperimentalEffectGoal:
    id: GoalId
    effect: str
    """Journal name of the experimental effect (``special_fsd_heavy``)."""
    module: str
    applications: int = 1

    def __post_init__(self) -> None:
        _require_name(self.effect, "experimental effect")
        _require_name(self.module, "module")
        if self.applications < 1:
            raise ValueError(f"a goal takes at least one application, not {self.applications}")


type Goal = BlueprintGoal | ExperimentalEffectGoal
