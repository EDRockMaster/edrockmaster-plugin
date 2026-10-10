"""Engineering: inventory, engineers, collection and goals (ADR 0017).

``EngineeringTracker`` is the aggregate root of the engineering context.

- The **inventory** is unknown until the game states it (``Materials``, at load)
  or EDMC does (its ``state``, when the plugin starts after the game); each
  change then applies to it. It is never stored. A material reaching its
  **cap** is reported: what is collected beyond it is lost.
- The **engineers**: their status and rank, as the game states them.
- A **collection** runs from the first change of materials to game close or
  reset; death does not end it (materials survive it). It counts what was
  gained per category and what was used, and the materials that reached
  their cap.
- **On foot** (ADR 0027, ``on_foot``): the ship locker and the backpack, and the
  suits and weapons seen. The player's own materials brought into the backpack
  count in the collection, by kind; what the backpack carried at a death is lost.
- The **goals**: what each one still misses, with the inventory, and the
  unlocked engineers who offer it. A goal is **ready** when nothing is missing
  for it alone. A roll of a blueprint, at the goal's grade, on the goal's
  module type, takes one roll off the first matching goal; an experimental
  effect, one application. A goal with nothing left is done and removed.

The tracker reports goal changes it makes (``GoalProgressed``, ``GoalDone``) so
that the application layer stores them; the player's own changes come through
``add_goal``, ``replace_goal`` and ``remove_goal``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import assert_never

from edrockmaster.domain.engineering.catalogue import (
    Catalogue,
    Ingredients,
    MaterialCategory,
    OnFootKind,
)
from edrockmaster.domain.engineering.goals import (
    BlueprintGoal,
    ExperimentalEffectGoal,
    Goal,
    GoalId,
)
from edrockmaster.domain.engineering.journal import (
    BlueprintApplied,
    ChangeCause,
    CommanderDied,
    EngineerProgressed,
    EngineersStated,
    EngineerState,
    EngineerStatus,
    Fact,
    GameClosed,
    InventoryStated,
    MaterialChange,
    MaterialsChanged,
)
from edrockmaster.domain.engineering.on_foot import Equipment, OnFoot, OnFootHolding
from edrockmaster.domain.engineering.on_foot_journal import (
    BackpackChanged,
    BackpackStated,
    Boarded,
    EquipmentSold,
    LoadoutChosen,
    LockerStated,
    Stock,
    SuitBought,
    WeaponBought,
    WeaponEquipped,
)

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


@dataclass(frozen=True, slots=True)
class GoalProgress:
    goal: Goal
    needed: Ingredients
    """Everything the goal takes, all rolls or applications included."""
    missing: Ingredients | None
    """What the inventory lacks for it; ``None`` while the inventory is unknown."""
    engineers: tuple[int, ...]
    """Unlocked engineers offering it on its module type."""
    known: bool = True
    """``False`` when the catalogue does not know its blueprint, grade or effect."""

    @property
    def ready(self) -> bool:
        return self.known and self.missing is not None and not self.missing


@dataclass(frozen=True, slots=True)
class EngineeringStats:
    collection: CollectionStats | None
    goals: tuple[GoalProgress, ...]
    inventory_known: bool
    on_foot_known: bool = False

    @property
    def goals_ready(self) -> int:
        return sum(1 for progress in self.goals if progress.ready)


@dataclass(frozen=True, slots=True)
class CollectionStarted:
    at: datetime


@dataclass(frozen=True, slots=True)
class CollectionEnded:
    at: datetime
    reason: CollectionEndReason


@dataclass(frozen=True, slots=True)
class EngineeringUpdated:
    stats: EngineeringStats
    progressed: bool
    """A change the player made in game (not a statement of the game at load)."""


@dataclass(frozen=True, slots=True)
class MaterialCapped:
    symbol: str
    name: str | None
    cap: int


@dataclass(frozen=True, slots=True)
class GoalReady:
    goal: Goal


@dataclass(frozen=True, slots=True)
class GoalProgressed:
    """A roll or an application was made: the goal has one fewer."""

    goal: Goal


@dataclass(frozen=True, slots=True)
class GoalDone:
    goal: Goal


type EngineeringNotification = (
    CollectionStarted
    | CollectionEnded
    | EngineeringUpdated
    | MaterialCapped
    | GoalReady
    | GoalProgressed
    | GoalDone
)


@dataclass(slots=True)
class _Collection:
    started_at: datetime
    gained: Counter[MaterialCategory | None] = field(default_factory=Counter)
    used: int = 0
    capped: list[str] = field(default_factory=list)
    gained_on_foot: Counter[OnFootKind] = field(default_factory=Counter)
    lost_on_foot: int = 0

    def stats(self) -> CollectionStats:
        return CollectionStats(
            self.started_at,
            dict(self.gained),
            self.used,
            tuple(self.capped),
            dict(self.gained_on_foot),
            self.lost_on_foot,
        )


class EngineeringTracker:
    def __init__(self, catalogue: Catalogue) -> None:
        self._catalogue = catalogue
        self._inventory: dict[str, int] | None = None
        self._names: dict[str, str] = {}
        self._engineers: dict[int, EngineerState] = {}
        self._goals: list[Goal] = []
        self._collection: _Collection | None = None
        self._ready: set[GoalId] = set()
        self._on_foot = OnFoot()

    @property
    def catalogue(self) -> Catalogue:
        return self._catalogue

    @property
    def inventory(self) -> Mapping[str, int] | None:
        """Count of each material held, by symbol; ``None`` until the game or EDMC states it."""
        return None if self._inventory is None else dict(self._inventory)

    @property
    def engineers(self) -> Mapping[int, EngineerState]:
        return dict(self._engineers)

    @property
    def goals(self) -> tuple[Goal, ...]:
        return tuple(self._goals)

    @property
    def on_foot_inventory(self) -> tuple[OnFootHolding, ...] | None:
        """Each on-foot material held; ``None`` until the game states the ship locker."""
        return self._on_foot.inventory()

    def on_foot_held(self) -> Mapping[str, int]:
        """The player's own on-foot materials, consumables aside: what counts towards goals."""
        return self._on_foot.held()

    @property
    def equipment(self) -> Mapping[int, Equipment]:
        """The suits and weapons the journal showed, by id, as last shown."""
        return self._on_foot.equipment

    def name_of(self, symbol: str) -> str | None:
        """A material's name in the game's language, once the journal gave it."""
        return self._names.get(symbol)

    def stats(self) -> EngineeringStats:
        return EngineeringStats(
            self._collection.stats() if self._collection else None,
            tuple(self._progress(goal) for goal in self._goals),
            self._inventory is not None,
            self._on_foot.known,
        )

    def shopping_list(self) -> Ingredients:
        """What the inventory lacks for all the goals together, by material."""
        needed: Counter[str] = Counter()
        for goal in self._goals:
            needed.update(self._needed(goal) or {})
        held = self._inventory or {}
        return {
            symbol: count - held.get(symbol, 0)
            for symbol, count in sorted(needed.items())
            if count > held.get(symbol, 0)
        }

    # The journal

    def handle(self, fact: Fact) -> list[EngineeringNotification]:  # noqa: PLR0911 - a case a fact
        match fact:
            case InventoryStated():
                self._inventory = {}
                self._apply(fact.counts)
                return self._after(progressed=False)
            case EngineersStated():
                self._engineers = {state.engineer_id: state for state in fact.engineers}
                return self._after(progressed=False)
            case EngineerProgressed():
                self._engineers[fact.engineer.engineer_id] = fact.engineer
                return self._after(progressed=False)
            case MaterialsChanged():
                return self._on_change(fact.at, fact.cause, fact.changes)
            case BlueprintApplied():
                return self._on_applied(fact)
            case GameClosed():
                return self.end(fact.at, CollectionEndReason.GAME_CLOSED)
            case (
                LockerStated() | BackpackStated() | BackpackChanged() | Boarded() | CommanderDied()
            ):
                return self._on_foot_stock(fact)
            case (
                LoadoutChosen() | WeaponEquipped() | WeaponBought() | SuitBought() | EquipmentSold()
            ):
                return self._on_foot_equipment(fact)
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(fact)

    def end(self, at: datetime, reason: CollectionEndReason) -> list[EngineeringNotification]:
        """End the collection (game closed, or the panel's reset button)."""
        if self._collection is None:
            return []
        self._collection = None
        return [CollectionEnded(at, reason), EngineeringUpdated(self.stats(), progressed=True)]

    # The player's goals

    def load_goals(self, goals: Iterable[Goal]) -> list[EngineeringNotification]:
        """The stored goals, at start; goals added meanwhile come after them."""
        loaded = list(goals)
        known = {goal.id for goal in loaded}
        self._goals = loaded + [goal for goal in self._goals if goal.id not in known]
        return self._after(progressed=False)

    def add_goal(self, goal: Goal) -> list[EngineeringNotification]:
        self._goals.append(goal)
        return self._after(progressed=False)

    def replace_goal(self, goal: Goal) -> list[EngineeringNotification]:
        self._goals = [goal if current.id == goal.id else current for current in self._goals]
        self._ready.discard(goal.id)
        return self._after(progressed=False)

    def remove_goal(self, goal_id: GoalId) -> list[EngineeringNotification]:
        self._goals = [goal for goal in self._goals if goal.id != goal_id]
        self._ready.discard(goal_id)
        return self._after(progressed=False)

    # Rules

    def _on_change(
        self, at: datetime, cause: ChangeCause, changes: tuple[MaterialChange, ...]
    ) -> list[EngineeringNotification]:
        return self._record(at, cause, changes) + self._after(progressed=True)

    def _record(
        self, at: datetime, cause: ChangeCause, changes: tuple[MaterialChange, ...]
    ) -> list[EngineeringNotification]:
        """Count the changes in the collection, which starts if needed, and apply them."""
        collection, notifications = self._collecting(at)
        for change in changes:
            if change.count > 0 and cause in _GAINS:
                collection.gained[self._category(change.symbol)] += change.count
            elif change.count < 0 and cause is not ChangeCause.TRADED:
                collection.used -= change.count
        capped = self._apply(changes)
        for symbol in capped:
            if symbol not in collection.capped:
                collection.capped.append(symbol)
        notifications += [
            MaterialCapped(symbol, self._names.get(symbol), self._catalogue.materials[symbol].cap)
            for symbol in capped
        ]
        return notifications

    def _on_foot_stock(
        self, fact: LockerStated | BackpackStated | BackpackChanged | Boarded | CommanderDied
    ) -> list[EngineeringNotification]:
        notifications: list[EngineeringNotification] = []
        progressed = False
        match fact:
            case LockerStated():
                self._name(fact.stock)
                self._on_foot.state_locker(fact.stock)
            case BackpackStated():
                self._name(fact.stock)
                self._on_foot.state_backpack(fact.stock)
            case BackpackChanged():
                self._name(fact.added + fact.removed)
                gained = self._on_foot.change_backpack(fact.added, fact.removed)
                if gained:
                    collection, notifications = self._collecting(fact.at)
                    collection.gained_on_foot.update(gained)
                    progressed = True
            case Boarded():
                self._on_foot.board()
            case CommanderDied():
                lost = self._on_foot.die()
                if lost:
                    collection, notifications = self._collecting(fact.at)
                    collection.lost_on_foot += lost
                    progressed = True
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(fact)
        return notifications + self._after(progressed)

    def _on_foot_equipment(
        self,
        fact: LoadoutChosen | WeaponEquipped | WeaponBought | SuitBought | EquipmentSold,
    ) -> list[EngineeringNotification]:
        match fact:
            case LoadoutChosen():
                self._on_foot.show(fact.suit, *fact.weapons)
            case WeaponEquipped() | WeaponBought():
                self._on_foot.show(fact.weapon)
            case SuitBought():
                self._on_foot.show(fact.suit)
            case EquipmentSold():
                self._on_foot.sold(fact.id)
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(fact)
        return self._after(progressed=False)

    def _collecting(self, at: datetime) -> tuple[_Collection, list[EngineeringNotification]]:
        """The collection, started if needed, and its start if it did."""
        if self._collection is not None:
            return self._collection, []
        self._collection = _Collection(at)
        return self._collection, [CollectionStarted(at)]

    def _name(self, stock: Iterable[Stock]) -> None:
        for item in stock:
            if item.name:
                self._names[item.symbol] = item.name

    def _on_applied(self, fact: BlueprintApplied) -> list[EngineeringNotification]:
        notifications = self._record(fact.at, ChangeCause.ENGINEERED, fact.spent)
        notifications += self._roll(fact)
        return notifications + self._after(progressed=True)

    def _roll(self, fact: BlueprintApplied) -> list[EngineeringNotification]:
        """Take one roll, or one application, off the first goal the craft made."""
        module = self._catalogue.module_of(fact.module_item)
        for index, goal in enumerate(self._goals):
            if not self._made_by(goal, fact, module.key if module else None):
                continue
            self._ready.discard(goal.id)
            after = _one_fewer(goal)
            if after is None:
                del self._goals[index]
                return [GoalDone(goal)]
            self._goals[index] = after
            return [GoalProgressed(after)]
        return []

    @staticmethod
    def _made_by(goal: Goal, fact: BlueprintApplied, module: str | None) -> bool:
        # An item the catalogue does not know matches any module type
        if module is not None and goal.module != module:
            return False
        match goal:
            case BlueprintGoal():
                return fact.effect is None and (goal.blueprint, goal.grade) == (
                    fact.blueprint,
                    fact.grade,
                )
            case ExperimentalEffectGoal():
                return fact.effect == goal.effect
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(goal)

    def _apply(self, changes: Iterable[MaterialChange]) -> list[str]:
        """Apply changes to the inventory, if known; return the materials that reached their cap."""
        capped = []
        for change in changes:
            if change.name:
                self._names[change.symbol] = change.name
            if self._inventory is None:
                continue
            before = self._inventory.get(change.symbol, 0)
            after = max(0, before + change.count)
            material = self._catalogue.materials.get(change.symbol)
            if material is not None and after >= material.cap:
                after = material.cap
                if before < material.cap and change.count > 0:
                    capped.append(change.symbol)
            self._inventory[change.symbol] = after
        return capped

    def _after(self, progressed: bool) -> list[EngineeringNotification]:
        """The update, and the goals that became ready."""
        stats = self.stats()
        ready = {progress.goal.id: progress.goal for progress in stats.goals if progress.ready}
        newly = [GoalReady(goal) for goal_id, goal in ready.items() if goal_id not in self._ready]
        self._ready = set(ready)
        return [*newly, EngineeringUpdated(stats, progressed or bool(newly))]

    def _category(self, symbol: str) -> MaterialCategory | None:
        material = self._catalogue.materials.get(symbol)
        return material.category if material else None

    def _needed(self, goal: Goal) -> Ingredients | None:
        match goal:
            case BlueprintGoal():
                blueprint = self._catalogue.blueprints.get(goal.blueprint)
                ingredients = blueprint.grades.get(goal.grade) if blueprint else None
                times = goal.rolls
            case ExperimentalEffectGoal():
                effect = self._catalogue.effects.get(goal.effect)
                ingredients = effect.ingredients if effect else None
                times = goal.applications
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(goal)
        if ingredients is None:
            return None
        return {symbol: count * times for symbol, count in ingredients.items()}

    def _progress(self, goal: Goal) -> GoalProgress:
        needed = self._needed(goal)
        if needed is None:
            return GoalProgress(goal, {}, None, (), known=False)
        missing = None
        if self._inventory is not None:
            held = self._inventory
            missing = {
                symbol: count - held.get(symbol, 0)
                for symbol, count in needed.items()
                if count > held.get(symbol, 0)
            }
        return GoalProgress(goal, needed, missing, self._engineers_for(goal))

    def _engineers_for(self, goal: Goal) -> tuple[int, ...]:
        module = self._catalogue.modules.get(goal.module)
        if module is None:
            return ()
        match goal:
            case BlueprintGoal():
                offering = module.engineers(goal.blueprint, goal.grade)
            case ExperimentalEffectGoal():
                # Any engineer who engineers this module type can apply its effects
                offering = tuple(
                    sorted(
                        {
                            id_
                            for grades in module.offers.values()
                            for ids in grades.values()
                            for id_ in ids
                        }
                    )
                )
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(goal)
        return tuple(
            id_
            for id_ in offering
            if (state := self._engineers.get(id_)) is not None
            and state.status is EngineerStatus.UNLOCKED
        )


def _one_fewer(goal: Goal) -> Goal | None:
    match goal:
        case BlueprintGoal():
            return replace(goal, rolls=goal.rolls - 1) if goal.rolls > 1 else None
        case ExperimentalEffectGoal():
            return (
                replace(goal, applications=goal.applications - 1) if goal.applications > 1 else None
            )
        case _:  # pragma: no cover - exhaustiveness checked by mypy
            assert_never(goal)
