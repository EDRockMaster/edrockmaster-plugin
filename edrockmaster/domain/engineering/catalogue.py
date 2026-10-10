"""The game data of engineering (ADR 0017, ADR 0027): materials, blueprints, effects, engineers.

The journal names materials, blueprints and experimental effects, but does not
give a material's grade or cap, the ingredients of a blueprint, or which
engineer offers it. These come from ``catalogue.json``, written by
``scripts/import_engineering_data.py`` from EDCD/FDevIDs and EDCD/coriolis-data
at pinned commits. The data is Frontier Developments' (see ``NOTICE``).

A **material** has a grade from 1 to 5, and the game caps how many of it a
commander holds: 300 at grade 1, then 50 fewer per grade, 100 at grade 5. A
**blueprint** has ingredients per grade, the same on every module; which
engineers offer a grade depends on the **module type**, which the journal
names through an item (``int_powerdistributor_size7_class5``). An
**experimental effect** has one set of ingredients.

On foot (ADR 0027), an **on-foot material** is of a kind (item, component,
data, consumable) and has no grade nor cap; the **on-foot engineers** are kept
apart from the ship engineers.

Names are in English; the plugin's catalogues translate them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

FORMAT = 2
"""The version of ``catalogue.json`` this code reads."""

GRADES = range(1, 6)
ARMOUR = "bh"
"""The module type of armour (bulkheads)."""
_CAPS = {1: 300, 2: 250, 3: 200, 4: 150, 5: 100}


class MaterialCategory(StrEnum):
    RAW = "raw"
    MANUFACTURED = "manufactured"
    ENCODED = "encoded"


class OnFootKind(StrEnum):
    ITEM = "item"
    COMPONENT = "component"
    DATA = "data"
    CONSUMABLE = "consumable"
    """Medkits, energy cells, grenades: engineering does not use them."""


type Ingredients = Mapping[str, int]
"""Count of each material, by journal symbol."""


@dataclass(frozen=True, slots=True)
class Material:
    symbol: str
    """As the journal writes it, in lower case (``chemicalmanipulators``)."""
    category: MaterialCategory
    grade: int
    english_name: str

    @property
    def cap(self) -> int:
        """The most a commander can hold; what is collected beyond it is lost."""
        return _CAPS[self.grade]


@dataclass(frozen=True, slots=True)
class OnFootMaterial:
    symbol: str
    """As the journal writes it, in lower case (``chemicalsample``)."""
    kind: OnFootKind
    english_name: str


@dataclass(frozen=True, slots=True)
class Blueprint:
    name: str
    """As the journal writes it (``FSD_LongRange``)."""
    english_name: str
    grades: Mapping[int, Ingredients]


@dataclass(frozen=True, slots=True)
class ExperimentalEffect:
    name: str
    """As the journal writes it (``special_fsd_heavy``)."""
    english_name: str
    ingredients: Ingredients


@dataclass(frozen=True, slots=True)
class ModuleType:
    key: str
    """The catalogue's own key (``fsd``): the journal names modules by size and class."""
    english_name: str
    offers: Mapping[str, Mapping[int, tuple[int, ...]]]
    """The engineers (ids) offering each grade of each blueprint, by blueprint name."""
    effects: tuple[str, ...]
    items: tuple[str, ...] = ()
    """Journal symbols of its items, in lower case."""

    def engineers(self, blueprint: str, grade: int) -> tuple[int, ...]:
        return self.offers.get(blueprint, {}).get(grade, ())


@dataclass(frozen=True, slots=True)
class Source:
    repository: str
    commit: str
    date: str


class CatalogueError(ValueError):
    """``catalogue.json`` is not what this code expects: a packaging mistake."""


@dataclass(frozen=True, slots=True)
class Catalogue:
    sources: tuple[Source, ...]
    materials: Mapping[str, Material]
    engineers: Mapping[int, str]
    """Engineer names, by the id the journal gives (``EngineerID``)."""
    blueprints: Mapping[str, Blueprint]
    effects: Mapping[str, ExperimentalEffect]
    modules: Mapping[str, ModuleType]
    on_foot_materials: Mapping[str, OnFootMaterial]
    on_foot_engineers: Mapping[int, str]
    """On-foot engineer names, by the id the journal gives (``EngineerID``)."""

    def module_of(self, item: str) -> ModuleType | None:
        """The module type of an item the journal names (``EngineerCraft.Module``)."""
        symbol = item.lower()
        for module in self.modules.values():
            if symbol in module.items:
                return module
        # Armour is named after the ship: "anaconda_armour_grade3", "sidewinder_armour_reactive"
        if "_armour_" in symbol:
            return self.modules.get(ARMOUR)
        return None

    @property
    def date(self) -> str:
        """Date of the most recent source: how current the data is."""
        return max(source.date for source in self.sources)

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> Catalogue:
        """Build the catalogue from the content of ``catalogue.json``, and check it."""
        if data.get("format") != FORMAT:
            raise CatalogueError(f"catalogue format {data.get('format')!r}, expected {FORMAT}")
        try:
            catalogue = cls(
                sources=tuple(Source(**source) for source in data["sources"]),
                materials={
                    symbol: Material(
                        symbol, MaterialCategory(entry["category"]), entry["grade"], entry["name"]
                    )
                    for symbol, entry in data["materials"].items()
                },
                engineers={int(id_): name for id_, name in data["engineers"].items()},
                blueprints={
                    name: Blueprint(
                        name,
                        entry["name"],
                        {
                            int(grade): dict(ingredients)
                            for grade, ingredients in entry["grades"].items()
                        },
                    )
                    for name, entry in data["blueprints"].items()
                },
                effects={
                    name: ExperimentalEffect(name, entry["name"], dict(entry["ingredients"]))
                    for name, entry in data["effects"].items()
                },
                modules={
                    key: ModuleType(
                        key,
                        entry["name"],
                        {
                            blueprint: {int(grade): tuple(ids) for grade, ids in grades.items()}
                            for blueprint, grades in entry["blueprints"].items()
                        },
                        tuple(entry["effects"]),
                        tuple(entry["items"]),
                    )
                    for key, entry in data["modules"].items()
                },
                on_foot_materials={
                    symbol: OnFootMaterial(symbol, OnFootKind(entry["kind"]), entry["name"])
                    for symbol, entry in data["on_foot_materials"].items()
                },
                on_foot_engineers={
                    int(id_): name for id_, name in data["on_foot_engineers"].items()
                },
            )
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise CatalogueError(f"malformed catalogue: {error!r}") from error
        catalogue._check()
        return catalogue

    def _check(self) -> None:
        for material in self.materials.values():
            if material.grade not in GRADES:
                raise CatalogueError(f"material {material.symbol!r} has grade {material.grade}")
        for blueprint in self.blueprints.values():
            for grade, ingredients in blueprint.grades.items():
                if grade not in GRADES:
                    raise CatalogueError(f"blueprint {blueprint.name!r} has grade {grade}")
                self._check_ingredients(f"blueprint {blueprint.name!r}", ingredients)
        for effect in self.effects.values():
            self._check_ingredients(f"effect {effect.name!r}", effect.ingredients)
        for module in self.modules.values():
            for offered, grades in module.offers.items():
                if offered not in self.blueprints:
                    raise CatalogueError(f"module {module.key!r}: unknown blueprint {offered!r}")
                unknown = {id_ for ids in grades.values() for id_ in ids} - set(self.engineers)
                if unknown:
                    raise CatalogueError(f"module {module.key!r}: unknown engineers {unknown}")
            for name in module.effects:
                if name not in self.effects:
                    raise CatalogueError(f"module {module.key!r}: unknown effect {name!r}")

    def _check_ingredients(self, what: str, ingredients: Ingredients) -> None:
        for symbol, count in ingredients.items():
            if symbol not in self.materials:
                raise CatalogueError(f"{what}: unknown material {symbol!r}")
            if count < 1:
                raise CatalogueError(f"{what}: {count} {symbol}")
