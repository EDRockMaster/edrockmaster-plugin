"""Display names of engineering: materials, blueprints, effects, module types, goals (ADR 0017).

A material shows the game's own name when the journal gave it (the game's
language), else the catalogue's English name, translated; the others always
come from the catalogue, translated. A name the catalogue lacks shows as the
journal writes it; so do all of them without a catalogue.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import assert_never

from edrockmaster.domain.engineering.catalogue import Catalogue
from edrockmaster.domain.engineering.goals import BlueprintGoal, ExperimentalEffectGoal, Goal
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
        return self._tl(material.english_name) if material else symbol

    def blueprint(self, name: str) -> str:
        blueprint = self._catalogue.blueprints.get(name) if self._catalogue else None
        return self._tl(blueprint.english_name) if blueprint else name

    def effect(self, name: str) -> str:
        effect = self._catalogue.effects.get(name) if self._catalogue else None
        return self._tl(effect.english_name) if effect else name

    def module(self, key: str) -> str:
        module = self._catalogue.modules.get(key) if self._catalogue else None
        return self._tl(module.english_name) if module else key

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
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(goal)
