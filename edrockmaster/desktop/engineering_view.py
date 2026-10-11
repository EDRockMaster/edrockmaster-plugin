"""The engineering view of the desktop application (ADR 0017, ADR 0020).

What ADR 0017 planned for a separate window, as a part of the live view: the
inventory (by category and grade, count and cap), the ship engineers (status,
rank), the goals (what each misses, the unlocked engineers offering it) and the
shopping list; and on foot (ADR 0027, ADR 0029), the materials held in the ship
locker and the backpack, the on-foot engineers, the suits and weapons seen, and
what moved to or from the player's fleet carrier, and the class upgrades with
their own shopping list and credits. Names come in the player's language:
materials as the game names them when the journal did, the rest translated
from the catalogue.

The goal form needs the catalogue (module types, their blueprints and grades,
their experimental effects; suits and weapons with their class upgrades): it
never changes, so the interface asks for it once (``catalogue_view``). A goal
the interface asks for is checked here and by the domain (``goal_from_request``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, assert_never

from edrockmaster.application.engineering_service import EngineeringService
from edrockmaster.domain.engineering.catalogue import (
    Catalogue,
    Ingredients,
    MaterialCategory,
    OnFootKind,
)
from edrockmaster.domain.engineering.goals import (
    BlueprintGoal,
    ClassUpgradeGoal,
    ExperimentalEffectGoal,
    Goal,
    GoalId,
)
from edrockmaster.domain.engineering.journal import EngineerStatus
from edrockmaster.domain.engineering.on_foot import CarrierMove, Equipment
from edrockmaster.domain.engineering.on_foot_journal import Suit
from edrockmaster.domain.engineering.session import GoalProgress
from edrockmaster.ui.engineering_names import EngineeringNames

_CATEGORY_ORDER = {
    MaterialCategory.RAW: 0,
    MaterialCategory.MANUFACTURED: 1,
    MaterialCategory.ENCODED: 2,
}
_KIND_ORDER = {kind: index for index, kind in enumerate(OnFootKind)}
BLUEPRINT = "blueprint"
EFFECT = "effect"
CLASS_UPGRADE = "classUpgrade"


def engineering_view(service: EngineeringService, names: EngineeringNames) -> dict[str, Any]:
    catalogue = service.catalogue
    inventory = service.inventory
    return {
        "inventoryKnown": inventory is not None,
        "materials": _materials(catalogue, inventory or {}, names),
        "engineers": _engineers(service, names),
        "goals": [
            _goal(progress, names)
            for progress in service.stats.goals
            if not isinstance(progress.goal, ClassUpgradeGoal)
        ],
        "shoppingList": _ingredients(service.shopping_list(), inventory or {}, names),
        "catalogueDate": catalogue.date,
        "onFoot": _on_foot(service, names),
    }


def _on_foot(service: EngineeringService, names: EngineeringNames) -> dict[str, Any]:
    inventory = service.on_foot_inventory
    held = service.on_foot_held()
    materials: list[dict[str, Any]] = [
        {
            "symbol": holding.symbol,
            "name": names.material(holding.symbol),
            "kind": holding.kind.value,
            "locker": holding.locker,
            "backpack": holding.backpack,
            "mission": holding.mission,
        }
        for holding in inventory or ()
    ]
    materials.sort(key=lambda row: (_KIND_ORDER[OnFootKind(row["kind"])], row["name"].casefold()))
    known = service.engineers
    engineers = [
        {
            "id": engineer_id,
            "name": names.engineer(engineer_id),
            "status": _status(state.status) if (state := known.get(engineer_id)) else None,
        }
        for engineer_id in service.catalogue.on_foot_engineers
    ]
    equipment: list[dict[str, Any]] = [
        {
            "id": piece.id,
            "kind": "suit",
            "symbol": piece.symbol,
            "name": names.item(piece.symbol),
            "class": piece.suit_class,
        }
        if isinstance(piece, Suit)
        else {
            "id": piece.id,
            "kind": "weapon",
            "symbol": piece.symbol,
            "name": piece.name or piece.symbol,
            "class": piece.weapon_class,
        }
        for piece in service.equipment.values()
    ]
    equipment.sort(key=lambda row: (row["kind"] != "suit", row["name"].casefold()))
    return {
        "known": inventory is not None,
        "materials": materials,
        "engineers": sorted(engineers, key=lambda row: row["name"].casefold()),
        "equipment": equipment,
        "carrierMoves": [_move(move, names) for move in service.carrier_moves],
        "goals": [
            _class_upgrade(progress, progress.goal, names)
            for progress in service.stats.goals
            if isinstance(progress.goal, ClassUpgradeGoal)
        ],
        "shoppingList": _ingredients(service.on_foot_shopping_list(), held, names),
        "credits": service.on_foot_credits(),
    }


def _class_upgrade(
    progress: GoalProgress, goal: ClassUpgradeGoal, names: EngineeringNames
) -> dict[str, Any]:
    return {
        "id": goal.id.value,
        "item": goal.item,
        "title": names.item(goal.item),
        "equipmentId": goal.equipment_id,
        "fromClass": goal.from_class,
        "toClass": goal.to_class,
        "known": progress.known,
        "unknownClasses": list(progress.unknown_classes),
        "unverified": progress.unverified,
        "credits": progress.credits,
        "ready": progress.ready,
        "missing": None if progress.missing is None else _ingredients(progress.missing, {}, names),
    }


def _move(move: CarrierMove, names: EngineeringNames) -> dict[str, Any]:
    return {
        "dockedAt": _instant(move.docked_at),
        "at": _instant(move.at),
        "materials": sorted(
            (
                {"symbol": symbol, "name": names.material(symbol), "count": count}
                for symbol, count in move.changes.items()
            ),
            key=lambda row: str(row["name"]).casefold(),
        ),
    }


def _instant(at: datetime) -> str:
    return at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _goal(progress: GoalProgress, names: EngineeringNames) -> dict[str, Any]:
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
        case ClassUpgradeGoal():  # pragma: no cover - in the on-foot part
            raise ValueError("a class upgrade is shown on foot")
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
    """What the goal form and the blueprints tab offer: module types, their blueprints with
    each grade's ingredients and engineers, their effects with their ingredients."""
    modules: list[dict[str, Any]] = []
    for key, module in catalogue.modules.items():
        blueprints: list[dict[str, Any]] = [
            {
                "name": name,
                "title": names.blueprint(name),
                "grades": sorted(module.offers[name]),
                "recipes": [
                    {
                        "grade": grade,
                        "ingredients": _recipe(
                            catalogue.blueprints[name].grades.get(grade, {}), names
                        ),
                        "engineers": list(module.offers[name][grade]),
                    }
                    for grade in sorted(module.offers[name])
                ],
            }
            for name in module.offers
            if name in catalogue.blueprints
        ]
        effects: list[dict[str, Any]] = [
            {
                "name": name,
                "title": names.effect(name),
                "ingredients": _recipe(catalogue.effects[name].ingredients, names)
                if name in catalogue.effects
                else [],
            }
            for name in module.effects
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
        "onFootItems": _on_foot_items(catalogue, names),
    }


def _on_foot_items(catalogue: Catalogue, names: EngineeringNames) -> list[dict[str, Any]]:
    """Suits then weapons, by name, with their known class upgrades (ADR 0027, ADR 0030)."""
    items = [
        {
            "symbol": item.symbol,
            "kind": item.kind.value,
            "name": names.item(item.symbol),
            "upgrades": [
                {
                    "toClass": upgrade.to_class,
                    "credits": upgrade.credits,
                    "confidence": upgrade.confidence.value,
                    "ingredients": _recipe(upgrade.ingredients, names),
                }
                for _, upgrade in sorted(item.upgrades.items())
            ],
        }
        for item in catalogue.on_foot_items.values()
    ]
    return sorted(items, key=lambda row: (row["kind"] != "suit", row["name"].casefold()))


def _recipe(ingredients: Ingredients, names: EngineeringNames) -> list[dict[str, Any]]:
    return [
        {"symbol": row["symbol"], "name": row["name"], "count": row["count"]}
        for row in _ingredients(ingredients, {}, names)
    ]


def goal_from_request(
    request: Mapping[str, Any],
    catalogue: Catalogue,
    equipment: Mapping[int, Equipment],
    now: datetime,
) -> Goal:
    """A new goal from the interface's form; ``ValueError`` if the catalogue does not offer it.

    A class upgrade of one of the player's items (``equipmentId``) starts from its class; of a
    type, from ``fromClass`` (1 by default)."""
    if request.get("kind") == CLASS_UPGRADE:
        return _class_upgrade_from_request(request, catalogue, equipment, now)
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


def _class_upgrade_from_request(
    request: Mapping[str, Any],
    catalogue: Catalogue,
    equipment: Mapping[int, Equipment],
    now: datetime,
) -> ClassUpgradeGoal:
    item, to_class = request.get("item"), request.get("toClass")
    equipment_id, from_class = request.get("equipmentId"), request.get("fromClass", 1)
    if not isinstance(item, str) or item not in catalogue.on_foot_items:
        raise ValueError(f"no such item for a goal: {item!r}")
    if not isinstance(to_class, int) or not isinstance(from_class, int):
        raise ValueError(f"not a class upgrade goal: {dict(request)!r}")
    if equipment_id is not None:
        piece = equipment.get(equipment_id) if isinstance(equipment_id, int) else None
        shown = (
            (piece.suit_class if isinstance(piece, Suit) else piece.weapon_class) if piece else None
        )
        if piece is None or piece.symbol != item or shown is None:
            raise ValueError(f"no item {equipment_id!r} of type {item!r} with a class")
        from_class = shown
    return ClassUpgradeGoal(GoalId.new(), item, from_class, to_class, now, equipment_id)


def with_count(goal: Goal, count: int) -> Goal:
    """The goal, with a new number of rolls or applications, or a new class aimed at
    (checked by the domain)."""
    match goal:
        case BlueprintGoal():
            return BlueprintGoal(goal.id, goal.blueprint, goal.module, goal.grade, count)
        case ExperimentalEffectGoal():
            return ExperimentalEffectGoal(goal.id, goal.effect, goal.module, count)
        case ClassUpgradeGoal():
            return replace(goal, to_class=count)
        case _:  # pragma: no cover - exhaustiveness checked by mypy
            assert_never(goal)
