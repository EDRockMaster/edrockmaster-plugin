"""How far a goal is (ADR 0017, ADR 0027, ADR 0031): what it takes, what is missing, who offers it.

Pure functions of the catalogue and of what the player holds, each goal on its own; the
priority between goals is ``reservation``'s.

- A **blueprint** or an **experimental effect**: its ingredients, times its rolls or
  applications, against the ship's materials; the unlocked engineers offering it on its
  module type.
- A **class upgrade** on foot (ADR 0027, ADR 0030): every step's ingredients and credits,
  against the on-foot materials; a step the catalogue does not know is said, and the goal
  is then never ready.
- A **modification** on foot: the recipe read on the goal's item type, and the unlocked
  engineers seen offering it; without such a recipe, the goal is unknown.
- An **engineer unlock** (ADR 0031): what is left to do for the engineer, from their sheet
  and their state: an on-foot engineer's referral while not known yet, a ship engineer's
  invitation while not invited, then the unlock. A task to give or sell given on-foot
  materials is counted against those held; any other is not, and the goal is then never
  ready.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import assert_never

from edrockmaster.domain.engineering.catalogue import (
    Catalogue,
    ClassUpgrade,
    Ingredients,
    ModificationRecipe,
    RecipeConfidence,
)
from edrockmaster.domain.engineering.goals import (
    BlueprintGoal,
    ClassUpgradeGoal,
    EngineerUnlockGoal,
    ExperimentalEffectGoal,
    Goal,
    ModificationGoal,
)
from edrockmaster.domain.engineering.journal import EngineerState, EngineerStatus


@dataclass(frozen=True, slots=True)
class GoalProgress:
    goal: Goal
    needed: Ingredients
    """Everything the goal takes, all rolls or applications included."""
    missing: Ingredients | None
    """What the inventory lacks for it; ``None`` while the inventory is unknown."""
    engineers: tuple[int, ...]
    """Unlocked engineers offering it on its module type; on foot, seen offering it."""
    known: bool = True
    """``False`` when the catalogue does not know its blueprint, grade or effect, a step
    of its class upgrade, or its modification on its item type."""
    credits: int = 0
    """On foot, the credits it takes: shown, not counted."""
    unknown_classes: tuple[int, ...] = ()
    """On foot, the classes whose upgrade the catalogue does not know."""
    unverified: bool = False
    """On foot, a recipe it takes was not seen in game: deduced or read elsewhere (ADR 0030)."""
    counted: bool = True
    """``False`` when what is left to do is not only materials held: a rank, a reputation, a
    commodity (an engineer unlock); the goal is then never ready."""
    ready_alone: bool = False
    """It would be ready without the goals above it in the priority (ADR 0033)."""

    @property
    def ready(self) -> bool:
        return self.known and self.counted and self.missing is not None and not self.missing


@dataclass(frozen=True, slots=True)
class Holdings:
    """What the player holds, as the journal last stated it."""

    ship: Mapping[str, int] | None
    """The ship's materials; ``None`` until the game states them."""
    on_foot: Mapping[str, int] | None
    """The player's own on-foot materials; ``None`` until the game states the ship locker."""
    engineers: Mapping[int, EngineerState]


def progress(goal: Goal, catalogue: Catalogue, holdings: Holdings) -> GoalProgress:
    """The goal's progress, as if it were the only one."""
    match goal:
        case ClassUpgradeGoal():
            return _class_progress(goal, catalogue, holdings)
        case ModificationGoal():
            return _modification_progress(goal, catalogue, holdings)
        case EngineerUnlockGoal():
            return _unlock_progress(goal, catalogue, holdings)
        case BlueprintGoal() | ExperimentalEffectGoal():
            ingredients = needed(goal, catalogue)
            if ingredients is None:
                return GoalProgress(goal, {}, None, (), known=False)
            lacking = None if holdings.ship is None else missing(ingredients, holdings.ship)
            engineers = _engineers_for(goal, catalogue, holdings.engineers)
            return GoalProgress(goal, ingredients, lacking, engineers)
        case _:  # pragma: no cover - exhaustiveness checked by mypy
            assert_never(goal)


def needed(
    goal: BlueprintGoal | ExperimentalEffectGoal, catalogue: Catalogue
) -> Ingredients | None:
    """What a ship goal takes, all its rolls or applications; ``None`` if the catalogue does
    not know it."""
    match goal:
        case BlueprintGoal():
            blueprint = catalogue.blueprints.get(goal.blueprint)
            ingredients = blueprint.grades.get(goal.grade) if blueprint else None
            times = goal.rolls
        case ExperimentalEffectGoal():
            effect = catalogue.effects.get(goal.effect)
            ingredients = effect.ingredients if effect else None
            times = goal.applications
        case _:  # pragma: no cover - exhaustiveness checked by mypy
            assert_never(goal)
    if ingredients is None:
        return None
    return {symbol: count * times for symbol, count in ingredients.items()}


def missing(needed: Mapping[str, int], held: Mapping[str, int]) -> Ingredients:
    """What ``held`` lacks for ``needed``, by material, in the materials' order."""
    return {
        symbol: count - held.get(symbol, 0)
        for symbol, count in sorted(needed.items())
        if count > held.get(symbol, 0)
    }


def _class_progress(
    goal: ClassUpgradeGoal, catalogue: Catalogue, holdings: Holdings
) -> GoalProgress:
    item = catalogue.on_foot_items.get(goal.item)
    steps: dict[int, ClassUpgrade | None] = {
        to_class: item.upgrades.get(to_class) if item else None for to_class in goal.steps
    }
    known = [upgrade for upgrade in steps.values() if upgrade is not None]
    ingredients: Counter[str] = Counter()
    for upgrade in known:
        ingredients.update(upgrade.ingredients)
    unknown = tuple(to_class for to_class, upgrade in steps.items() if upgrade is None)
    return GoalProgress(
        goal,
        dict(sorted(ingredients.items())),
        _on_foot_missing(ingredients, holdings),
        (),
        known=not unknown,
        credits=sum(upgrade.credits for upgrade in known),
        unknown_classes=unknown,
        unverified=any(upgrade.confidence is not RecipeConfidence.GAME for upgrade in known),
    )


def _modification_progress(
    goal: ModificationGoal, catalogue: Catalogue, holdings: Holdings
) -> GoalProgress:
    modification = catalogue.on_foot_modifications.get(goal.modification)
    recipe: ModificationRecipe | None = modification.recipe_for(goal.item) if modification else None
    engineers = _unlocked(modification.engineers, holdings.engineers) if modification else ()
    if recipe is None:
        return GoalProgress(goal, {}, None, engineers, known=False)
    return GoalProgress(
        goal,
        dict(sorted(recipe.ingredients.items())),
        _on_foot_missing(recipe.ingredients, holdings),
        engineers,
        credits=recipe.credits,
        unverified=recipe.confidence is not RecipeConfidence.GAME,
    )


def _unlock_progress(
    goal: EngineerUnlockGoal, catalogue: Catalogue, holdings: Holdings
) -> GoalProgress:
    details = catalogue.engineer_details.get(goal.engineer_id)
    if details is None:
        return GoalProgress(goal, {}, None, (), known=False, counted=False)
    state = holdings.engineers.get(goal.engineer_id)
    status = state.status if state else None
    ingredients: Counter[str] = Counter()
    # Each step left: counted when it is to give or sell given on-foot materials
    counted = status is not EngineerStatus.BARRED
    if status is None and details.referred_by:
        for referrer in details.referred_by:
            gives = catalogue.engineer_details[referrer].referral_gives
            ingredients.update(gives)
            counted = counted and bool(gives)
    if details.invitation is not None and status in (None, EngineerStatus.KNOWN):
        counted = False
    ingredients.update(details.unlock_gives)
    counted = counted and bool(details.unlock_gives)
    return GoalProgress(
        goal,
        dict(sorted(ingredients.items())),
        _on_foot_missing(ingredients, holdings),
        (),
        unverified=details.confidence is not RecipeConfidence.GAME,
        counted=counted,
    )


def _on_foot_missing(ingredients: Mapping[str, int], holdings: Holdings) -> Ingredients | None:
    return None if holdings.on_foot is None else missing(ingredients, holdings.on_foot)


def _engineers_for(
    goal: BlueprintGoal | ExperimentalEffectGoal,
    catalogue: Catalogue,
    engineers: Mapping[int, EngineerState],
) -> tuple[int, ...]:
    module = catalogue.modules.get(goal.module)
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
    return _unlocked(offering, engineers)


def _unlocked(offering: Iterable[int], engineers: Mapping[int, EngineerState]) -> tuple[int, ...]:
    return tuple(
        id_
        for id_ in offering
        if (state := engineers.get(id_)) is not None and state.status is EngineerStatus.UNLOCKED
    )
