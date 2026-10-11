"""Display names of engineering: materials, blueprints, effects, module types, engineers, goals
(ADR 0017), suits and weapons (ADR 0027).

A material shows the game's own name when the journal gave it (the game's
language), else the catalogue's English name, translated (on foot, as it is); the others always
come from the catalogue, translated. Suits are named by the catalogue too: the
journal names them by a key of the game's own (``$UtilitySuit_Class1_Name;``);
weapons keep their maker's name (``Karma C-44``), as the game writes it. A
name the catalogue lacks shows as the journal writes it; so do all of them
without a catalogue.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import assert_never

from edrockmaster.domain.engineering.catalogue import Catalogue, EquipmentKind
from edrockmaster.domain.engineering.goals import (
    BlueprintGoal,
    ClassUpgradeGoal,
    ExperimentalEffectGoal,
    Goal,
)
from edrockmaster.ui.panel_model import Translate


class EngineeringNames:
    def __init__(
        self,
        catalogue: Catalogue | None,
        translate: Translate,
        game_name: Callable[[str], str | None] = lambda _symbol: None,
    ) -> None:
        self._catalogue = catalogue
        self._tl = translate
        self._game_name = game_name

    def material(self, symbol: str) -> str:
        if name := self._game_name(symbol):
            return name
        material = self._catalogue.materials.get(symbol) if self._catalogue else None
        if material:
            return self._tl(material.english_name)
        # On foot (ADR 0027), the game names nearly every material in its language; those it
        # leaves unnamed are proper names (Insight, Kompromat, RDX), kept as the catalogue has them
        on_foot = self._catalogue.on_foot_materials.get(symbol) if self._catalogue else None
        return on_foot.english_name if on_foot else symbol

    def blueprint(self, name: str) -> str:
        blueprint = self._catalogue.blueprints.get(name) if self._catalogue else None
        return self._tl(blueprint.english_name) if blueprint else name

    def effect(self, name: str) -> str:
        effect = self._catalogue.effects.get(name) if self._catalogue else None
        return self._tl(effect.english_name) if effect else name

    def module(self, key: str) -> str:
        module = self._catalogue.modules.get(key) if self._catalogue else None
        return self._tl(module.english_name) if module else key

    def engineer(self, engineer_id: int) -> str:
        """Most keep their name; a title is translated (``Professor Palin``)."""
        name = self._catalogue.engineers.get(engineer_id) if self._catalogue else None
        if name is None and self._catalogue:
            name = self._catalogue.on_foot_engineers.get(engineer_id)
        return self._tl(name) if name else str(engineer_id)

    def item(self, symbol: str) -> str:
        """A suit or a weapon, by its journal symbol without class."""
        item = self._catalogue.on_foot_items.get(symbol) if self._catalogue else None
        if item is None:
            return symbol
        return self._tl(item.english_name) if item.kind is EquipmentKind.SUIT else item.english_name

    def goal(self, goal: Goal) -> str:
        """``Frame shift drive: Increased range, grade 5``."""
        match goal:
            case BlueprintGoal():
                return self._tl("{module}: {blueprint}, grade {grade}").format(
                    module=self.module(goal.module),
                    blueprint=self.blueprint(goal.blueprint),
                    grade=goal.grade,
                )
            case ExperimentalEffectGoal():
                return self._tl("{module}: {effect}").format(
                    module=self.module(goal.module), effect=self.effect(goal.effect)
                )
            case ClassUpgradeGoal():
                return self._tl("{item}: class {from_class} to {to_class}").format(
                    item=self.item(goal.item), from_class=goal.from_class, to_class=goal.to_class
                )
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(goal)
