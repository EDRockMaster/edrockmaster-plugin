"""Goals: what the player aims at in engineering (ADR 0017, ADR 0027).

A goal is a **blueprint** at a grade, with the number of **rolls** the player
expects to need, or an **experimental effect**, with a number of
**applications**. The game does not tell how many rolls a grade takes (it
depends on the engineer's rank and on luck): the player sets it, one by default.

On foot (ADR 0027), a **class upgrade** raises a suit or a weapon from one class
to a higher one, a step at a time. It names the type of item by its journal
symbol and, when the player chose one of theirs, that item's id: the goal then
follows that item only. Without it, any item of the type the journal shows
after the goal was set counts.

A goal names its blueprint or effect by its journal name, and the module it is
for by the catalogue's module key: the engineers offering a grade depend on the
module. Goals are the player's own and are stored (ADR 0018); their identity
is chosen when they are made, so that they can be stored without waiting for
the storage.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

MAX_GRADE = 5
MIN_CLASS = 1
MAX_CLASS = 5


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


@dataclass(frozen=True, slots=True)
class ClassUpgradeGoal:
    id: GoalId
    item: str
    """Journal symbol of the suit or weapon type, in lower case, without class
    (``tacticalsuit``, ``wpn_m_assaultrifle_kinetic_fauto``)."""
    from_class: int
    to_class: int
    set_at: datetime
    equipment_id: int | None = None
    """The player's own item it follows (``SuitID``, ``SuitModuleID``), if they chose one."""

    def __post_init__(self) -> None:
        _require_name(self.item, "item")
        if not MIN_CLASS <= self.from_class < self.to_class <= MAX_CLASS:
            raise ValueError(
                f"a class upgrade goes up from class {MIN_CLASS} to {MAX_CLASS}, "
                f"not from {self.from_class} to {self.to_class}"
            )
        if self.set_at.tzinfo is None:
            raise ValueError("the time a goal was set needs its time zone")

    @property
    def steps(self) -> tuple[int, ...]:
        """The classes it rises to, one step each."""
        return tuple(range(self.from_class + 1, self.to_class + 1))


type Goal = BlueprintGoal | ExperimentalEffectGoal | ClassUpgradeGoal
