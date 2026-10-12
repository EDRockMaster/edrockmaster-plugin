"""Engineering: inventory, engineers, collection and goals (ADR 0017).

``EngineeringTracker`` is the aggregate root of the engineering context: journal facts
in, its state changed, notifications (``events``) out.

- The **inventory** is unknown until the game states it (``Materials``, at load); each
  change then applies to it. It is never stored. A material reaching its **cap** is
  reported: what is collected beyond it is lost.
- The **engineers**: their status and rank, as the game states them.
- The **collection** (``collection``): from the first change of materials to game close
  or reset.
- **On foot** (ADR 0027, ``on_foot``): the ship locker and the backpack, and the suits
  and weapons seen.
- The **goals**, in the player's order, their priority. How far each one is comes from
  ``progress``, the share of the materials each takes from ``reservation`` (ADR 0033).
  The tracker moves them: a roll of a blueprint, at the goal's grade, on the goal's
  module type, takes one roll off the first matching goal; an experimental effect, one
  application. On foot, when the journal shows the goal's item (or, for a goal on a
  type, an item of it shown after the goal was set) at a higher class, a class upgrade
  starts from there, and at the class aimed at it is done; shown with the modification,
  a modification goal is done. An engineer unlock is done once the game states the
  engineer unlocked. A goal with nothing left is done and removed.

The tracker reports goal changes it makes (``GoalProgressed``, ``GoalDone``) so that the
application layer stores them; the player's own changes come through ``add_goal``,
``replace_goal`` and ``remove_goal``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import datetime
from typing import assert_never

from edrockmaster.domain.engineering.catalogue import (
    Catalogue,
    Ingredients,
    MaterialCategory,
)
from edrockmaster.domain.engineering.collection import Collection, CollectionEndReason
from edrockmaster.domain.engineering.events import (
    CollectionEnded,
    CollectionStarted,
    EngineeringNotification,
    EngineeringStats,
    EngineeringUpdated,
    GoalDone,
    GoalProgressed,
    GoalReady,
    MaterialCapped,
)
from edrockmaster.domain.engineering.goals import (
    BlueprintGoal,
    ClassUpgradeGoal,
    EngineerUnlockGoal,
    ExperimentalEffectGoal,
    Goal,
    GoalId,
    ModificationGoal,
    OnFootGoal,
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
from edrockmaster.domain.engineering.on_foot import (
    CarrierMove,
    Equipment,
    OnFoot,
    OnFootHolding,
)
from edrockmaster.domain.engineering.on_foot_journal import (
    BackpackChanged,
    BackpackStated,
    Boarded,
    CarrierKnown,
    DockedAt,
    EquipmentSold,
    LoadoutChosen,
    LockerStated,
    Stock,
    Suit,
    SuitBought,
    Undocked,
    Weapon,
    WeaponBought,
    WeaponEquipped,
)
from edrockmaster.domain.engineering.progress import GoalProgress, Holdings, missing, progress
from edrockmaster.domain.engineering.progress import needed as ship_needed
from edrockmaster.domain.engineering.reservation import reserve


class EngineeringTracker:
    def __init__(self, catalogue: Catalogue) -> None:
        self._catalogue = catalogue
        self._inventory: dict[str, int] | None = None
        self._names: dict[str, str] = {}
        self._engineers: dict[int, EngineerState] = {}
        self._goals: list[Goal] = []
        self._collection: Collection | None = None
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

    @property
    def carrier_moves(self) -> tuple[CarrierMove, ...]:
        """On-foot materials moved to or from the player's carrier (ADR 0029)."""
        return self._on_foot.carrier_moves

    def name_of(self, symbol: str) -> str | None:
        """A material's name in the game's language, once the journal gave it."""
        return self._names.get(symbol)

    def stats(self) -> EngineeringStats:
        holdings = self._holdings()
        alone = (progress(goal, self._catalogue, holdings) for goal in self._goals)
        return EngineeringStats(
            self._collection.stats() if self._collection else None,
            reserve(alone, self._inventory or {}, self._on_foot.held()),
            self._inventory is not None,
        )

    def shopping_list(self) -> Ingredients:
        """What the inventory lacks for all the ship goals together, by material."""
        needed: Counter[str] = Counter()
        for goal in self._goals:
            if isinstance(goal, BlueprintGoal | ExperimentalEffectGoal):
                needed.update(ship_needed(goal, self._catalogue) or {})
        return missing(needed, self._inventory or {})

    def on_foot_shopping_list(self) -> Ingredients:
        """What the on-foot materials held lack for all the on-foot goals together."""
        needed: Counter[str] = Counter()
        for goal in self._on_foot_goals():
            needed.update(self._progress(goal).needed)
        return missing(needed, self._on_foot.held())

    def on_foot_credits(self) -> int:
        """The credits all the on-foot goals take: shown, not counted."""
        return sum(self._progress(goal).credits for goal in self._on_foot_goals())

    # The journal

    def handle(self, fact: Fact) -> list[EngineeringNotification]:  # noqa: PLR0911 - a case a fact
        match fact:
            case InventoryStated():
                self._inventory = {}
                self._apply(fact.counts)
                return self._after(progressed=False)
            case EngineersStated():
                self._engineers = {state.engineer_id: state for state in fact.engineers}
                notifications = self._unlocks_done()
                return notifications + self._after(progressed=bool(notifications))
            case EngineerProgressed():
                self._engineers[fact.engineer.engineer_id] = fact.engineer
                notifications = self._unlocks_done()
                return notifications + self._after(progressed=bool(notifications))
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
            case CarrierKnown():
                self._on_foot.know_carrier(fact.carrier_id)
                return []
            case DockedAt():
                self._on_foot.dock(fact.at, fact.market_id)
                return []
            case Undocked():
                self._on_foot.undock()
                return []
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

    def order_goals(self, order: Iterable[GoalId]) -> list[EngineeringNotification]:
        """The player's new priority (ADR 0033): the goals it names first, in its order, then
        the others as they were; an id no goal has is ignored."""
        by_id = {goal.id: goal for goal in self._goals}
        named = list(dict.fromkeys(goal_id for goal_id in order if goal_id in by_id))
        rest = [goal for goal in self._goals if goal.id not in named]
        self._goals = [by_id[goal_id] for goal_id in named] + rest
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
        collection.count(cause, changes, self._category)
        capped = self._apply(changes)
        collection.cap(capped)
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
                self._on_foot.state_locker(fact.at, fact.stock)
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
        pieces: tuple[Suit | Weapon, ...]
        match fact:
            case LoadoutChosen():
                pieces = (fact.suit, *fact.weapons)
            case WeaponEquipped() | WeaponBought():
                pieces = (fact.weapon,)
            case SuitBought():
                pieces = (fact.suit,)
            case EquipmentSold():
                self._on_foot.sold(fact.id)
                return self._after(progressed=False)
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(fact)
        self._on_foot.show(*pieces)
        notifications = self._raise(fact.at, pieces)
        return notifications + self._after(progressed=bool(notifications))

    def _raise(
        self, at: datetime, pieces: Iterable[Suit | Weapon]
    ) -> list[EngineeringNotification]:
        """Move the on-foot goals of the items shown: a class upgrade started higher, or a goal
        done."""
        notifications: list[EngineeringNotification] = []
        for piece in pieces:
            goals: list[Goal] = []
            for goal in self._goals:
                if not isinstance(goal, ClassUpgradeGoal | ModificationGoal) or not _shows(
                    goal, piece, at
                ):
                    goals.append(goal)
                    continue
                after = _moved(goal, piece)
                if after is not goal:
                    self._ready.discard(goal.id)
                    notifications.append(GoalDone(goal) if after is None else GoalProgressed(after))
                if after is not None:
                    goals.append(after)
            self._goals = goals
        return notifications

    def _unlocks_done(self) -> list[EngineeringNotification]:
        """The engineer unlocks the game now states done."""
        notifications: list[EngineeringNotification] = []
        goals: list[Goal] = []
        for goal in self._goals:
            state = (
                self._engineers.get(goal.engineer_id)
                if isinstance(goal, EngineerUnlockGoal)
                else None
            )
            if state is not None and state.status is EngineerStatus.UNLOCKED:
                self._ready.discard(goal.id)
                notifications.append(GoalDone(goal))
            else:
                goals.append(goal)
        self._goals = goals
        return notifications

    def _collecting(self, at: datetime) -> tuple[Collection, list[EngineeringNotification]]:
        """The collection, started if needed, and its start if it did."""
        if self._collection is not None:
            return self._collection, []
        self._collection = Collection(at)
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
            if not isinstance(goal, BlueprintGoal | ExperimentalEffectGoal):
                continue
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
    def _made_by(
        goal: BlueprintGoal | ExperimentalEffectGoal, fact: BlueprintApplied, module: str | None
    ) -> bool:
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

    def _holdings(self) -> Holdings:
        on_foot = self._on_foot.held() if self._on_foot.known else None
        return Holdings(self._inventory, on_foot, self._engineers)

    def _progress(self, goal: Goal) -> GoalProgress:
        return progress(goal, self._catalogue, self._holdings())

    def _on_foot_goals(self) -> list[OnFootGoal | EngineerUnlockGoal]:
        """The goals that take on-foot materials."""
        return [
            goal
            for goal in self._goals
            if isinstance(goal, ClassUpgradeGoal | ModificationGoal | EngineerUnlockGoal)
        ]


def _moved(goal: OnFootGoal, piece: Suit | Weapon) -> OnFootGoal | None:
    """The goal once its item is shown: the same, started higher, or ``None`` when done."""
    match goal:
        case ClassUpgradeGoal():
            shown = piece.suit_class if isinstance(piece, Suit) else piece.weapon_class
            if shown is None:  # the flight suit has no class
                return goal
            if shown >= goal.to_class:
                return None
            return replace(goal, from_class=shown) if shown > goal.from_class else goal
        case ModificationGoal():
            return None if goal.modification in piece.mods else goal
        case _:  # pragma: no cover - exhaustiveness checked by mypy
            assert_never(goal)


def _shows(goal: OnFootGoal, piece: Suit | Weapon, at: datetime) -> bool:
    """The item shown is the goal's own, or one of its type shown after it was set."""
    if goal.equipment_id is not None:
        return piece.id == goal.equipment_id
    return piece.symbol == goal.item and at > goal.set_at


def _one_fewer(goal: BlueprintGoal | ExperimentalEffectGoal) -> Goal | None:
    match goal:
        case BlueprintGoal():
            return replace(goal, rolls=goal.rolls - 1) if goal.rolls > 1 else None
        case ExperimentalEffectGoal():
            return (
                replace(goal, applications=goal.applications - 1) if goal.applications > 1 else None
            )
        case _:  # pragma: no cover - exhaustiveness checked by mypy
            assert_never(goal)
