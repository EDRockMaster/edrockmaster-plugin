"""The engineering view of the desktop application (ADR 0017, ADR 0020).

What ADR 0017 planned for a separate window, as a part of the live view: the
inventory (by category and grade, count and cap), the ship engineers (status,
rank), the goals (what each misses, the unlocked engineers offering it) and the
shopping list. Names come in the player's language: materials as the game
names them when the journal did, the rest translated from the catalogue.

The goal form needs the catalogue (module types, their blueprints and grades,
their experimental effects): it never changes, so the interface asks for it
once (``catalogue_view``). A goal the interface asks for is checked here and by
the domain (``goal_from_request``).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, assert_never

from edrockmaster.application.engineering_service import EngineeringService
from edrockmaster.domain.engineering.catalogue import Catalogue, Ingredients, MaterialCategory
from edrockmaster.domain.engineering.goals import (
    BlueprintGoal,
    ExperimentalEffectGoal,
    Goal,
    GoalId,
)
from edrockmaster.domain.engineering.journal import EngineerStatus
from edrockmaster.domain.engineering.session import GoalProgress
from edrockmaster.ui.engineering_names import EngineeringNames

_CATEGORY_ORDER = {
    MaterialCategory.RAW: 0,
    MaterialCategory.MANUFACTURED: 1,
    MaterialCategory.ENCODED: 2,
}
BLUEPRINT = "blueprint"
EFFECT = "effect"


def engineering_view(service: EngineeringService, names: EngineeringNames) -> dict[str, Any]:
    catalogue = service.catalogue
    inventory = service.inventory
    return {
        "inventoryKnown": inventory is not None,
        "materials": _materials(catalogue, inventory or {}, names),
        "engineers": _engineers(service, names),
        "goals": [_goal(progress, catalogue, names) for progress in service.stats.goals],
        "shoppingList": _ingredients(service.shopping_list(), inventory or {}, names),
        "catalogueDate": catalogue.date,
    }


def _materials(
    catalogue: Catalogue, inventory: Mapping[str, int], names: EngineeringNames
) -> list[dict[str, Any]]:
    """Every material of the catalogue, held or not, and those held the catalogue lacks."""
    rows = []
    for symbol in sorted(set(catalogue.materials) | set(inventory)):
        material = catalogue.materials.get(symbol)
        rows.append(
            {
                "symbol": symbol,
                "name": names.material(symbol),
                "category": material.category.value if material else None,
                "grade": material.grade if material else None,
                "count": inventory.get(symbol, 0),
                "cap": material.cap if material else None,
            }
        )

    def order(row: dict[str, Any]) -> tuple[int, int, str]:
        category = MaterialCategory(row["category"]) if row["category"] else None
        return (
            _CATEGORY_ORDER[category] if category else len(_CATEGORY_ORDER),
            row["grade"] or 0,
            row["name"].casefold(),
        )

    return sorted(rows, key=order)


def _engineers(service: EngineeringService, names: EngineeringNames) -> list[dict[str, Any]]:
    """The ship engineers of the catalogue, with what the game says of them."""
    known = service.engineers
    rows = []
    for engineer_id in service.catalogue.engineers:
        state = known.get(engineer_id)
        rows.append(
            {
                "id": engineer_id,
                "name": names.engineer(engineer_id),
                "status": _status(state.status) if state else None,
                "rank": state.rank if state else None,
            }
        )
    return sorted(rows, key=lambda row: row["name"].casefold())


def _status(status: EngineerStatus) -> str:
    return status.name.lower()


def _goal(progress: GoalProgress, catalogue: Catalogue, names: EngineeringNames) -> dict[str, Any]:
    goal = progress.goal
    grade: int | None
    match goal:
        case BlueprintGoal():
            kind, title, grade, count = (
                BLUEPRINT,
                names.blueprint(goal.blueprint),
                goal.grade,
                goal.rolls,
            )
        case ExperimentalEffectGoal():
            kind, title, grade, count = EFFECT, names.effect(goal.effect), None, goal.applications
        case _:  # pragma: no cover - exhaustiveness checked by mypy
            assert_never(goal)
    return {
        "id": goal.id.value,
        "kind": kind,
        "title": title,
        "module": names.module(goal.module),
        "grade": grade,
        "count": count,
        "known": progress.known,
        "ready": progress.ready,
        "missing": None if progress.missing is None else _ingredients(progress.missing, {}, names),
        "engineers": [names.engineer(id_) for id_ in progress.engineers],
    }


def _ingredients(
    ingredients: Ingredients, inventory: Mapping[str, int], names: EngineeringNames
) -> list[dict[str, Any]]:
    return [
        {
            "symbol": symbol,
            "name": names.material(symbol),
            "count": count,
            "held": inventory.get(symbol, 0),
        }
        for symbol, count in sorted(ingredients.items(), key=lambda item: names.material(item[0]))
    ]


def catalogue_view(catalogue: Catalogue, names: EngineeringNames) -> dict[str, Any]:
    """What the goal form offers: module types, their blueprints with grades, their effects."""
    modules: list[dict[str, Any]] = []
    for key, module in catalogue.modules.items():
        blueprints: list[dict[str, Any]] = [
            {
                "name": name,
                "title": names.blueprint(name),
                "grades": sorted(module.offers[name]),
            }
            for name in module.offers
            if name in catalogue.blueprints
        ]
        effects: list[dict[str, Any]] = [
            {"name": name, "title": names.effect(name)} for name in module.effects
        ]
        modules.append(
            {
                "key": key,
                "name": names.module(key),
                "blueprints": sorted(blueprints, key=lambda row: row["title"].casefold()),
                "effects": sorted(effects, key=lambda row: row["title"].casefold()),
            }
        )
    return {
        "date": catalogue.date,
        "modules": sorted(modules, key=lambda row: row["name"].casefold()),
    }


def goal_from_request(request: Mapping[str, Any], catalogue: Catalogue) -> Goal:
    """A new goal from the interface's form; ``ValueError`` if the catalogue does not offer it."""
    kind, module_key, name = request.get("kind"), request.get("module"), request.get("name")
    count = request.get("count", 1)
    module = catalogue.modules.get(module_key) if isinstance(module_key, str) else None
    if module is None or not isinstance(name, str) or not isinstance(count, int):
        raise ValueError(f"not a goal: {dict(request)!r}")
    if kind == BLUEPRINT:
        grade = request.get("grade")
        if not isinstance(grade, int) or grade not in module.offers.get(name, {}):
            raise ValueError(f"module {module_key!r} offers no grade {grade!r} of {name!r}")
        return BlueprintGoal(GoalId.new(), name, module.key, grade, count)
    if kind == EFFECT:
        if name not in module.effects:
            raise ValueError(f"module {module_key!r} offers no effect {name!r}")
        return ExperimentalEffectGoal(GoalId.new(), name, module.key, count)
    raise ValueError(f"unknown kind of goal {kind!r}")


def with_count(goal: Goal, count: int) -> Goal:
    """The goal, with a new number of rolls or applications (checked by the domain)."""
    match goal:
        case BlueprintGoal():
            return BlueprintGoal(goal.id, goal.blueprint, goal.module, goal.grade, count)
        case ExperimentalEffectGoal():
            return ExperimentalEffectGoal(goal.id, goal.effect, goal.module, count)
        case _:  # pragma: no cover - exhaustiveness checked by mypy
            assert_never(goal)
