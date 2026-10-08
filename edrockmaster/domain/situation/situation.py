"""The commander's situation, as the journal tells it (ADR 0023).

``SituationTracker`` is the aggregate root of the situation context. Each part
of the situation is unknown until the journal gives it. The ship's type comes
in the game's language from ``LoadGame`` and ``ShipyardSwap``; ``Loadout`` only
names it by its symbol, so the tracker remembers the names it has seen.
Closing the game keeps the last known situation and says the game is closed;
the next ``LoadGame`` opens it again. The situation is kept in memory only:
never stored, never uploaded.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import assert_never

from edrockmaster.domain.situation.journal import (
    CommanderNamed,
    DockedAt,
    Fact,
    GameClosed,
    GameLoaded,
    GameMode,
    Located,
    OnFoot,
    Ship,
    ShipChanged,
    ShipRenamed,
    SystemReached,
    Undocked,
    WingAdded,
    WingJoined,
    WingLeft,
)


@dataclass(frozen=True, slots=True)
class Situation:
    commander: str | None = None
    ship: Ship | None = None
    on_foot: bool = False
    system: str | None = None
    station: str | None = None
    """The station or fleet carrier the commander is docked at."""
    mode: GameMode | None = None
    group: str | None = None
    """The private group's name, in that game mode."""
    wing: tuple[str, ...] = ()
    """The other members of the commander's wing."""
    game_running: bool = False


@dataclass(frozen=True, slots=True)
class SituationChanged:
    situation: Situation


class SituationTracker:
    def __init__(self) -> None:
        self._situation = Situation()
        self._type_names: dict[str, str] = {}

    @property
    def situation(self) -> Situation:
        return self._situation

    def handle(self, fact: Fact) -> list[SituationChanged]:
        before = self._situation
        self._situation = self._apply(before, fact)
        return [SituationChanged(self._situation)] if self._situation != before else []

    def _apply(self, now: Situation, fact: Fact) -> Situation:  # noqa: PLR0911, PLR0912 - a case a fact
        match fact:
            case CommanderNamed(name=name):
                return replace(now, commander=name, game_running=True)
            case GameLoaded():
                return replace(
                    now,
                    commander=fact.commander or now.commander,
                    ship=self._named(fact.ship) if fact.ship else now.ship,
                    on_foot=fact.ship is None and now.on_foot,
                    mode=fact.mode,
                    group=fact.group,
                    wing=(),
                    game_running=True,
                )
            case Located(system=system, station=station):
                return replace(now, system=system, station=station, game_running=True)
            case SystemReached(system=system):
                return replace(now, system=system, station=None)
            case DockedAt(station=station, system=system):
                return replace(now, station=station, system=system or now.system)
            case Undocked():
                return replace(now, station=None)
            case ShipChanged(ship=ship):
                return replace(now, ship=self._named(ship), on_foot=False)
            case ShipRenamed(name=name, ident=ident):
                if now.ship is None:
                    return now
                return replace(now, ship=replace(now.ship, name=name, ident=ident))
            case OnFoot(on_foot=on_foot):
                return replace(now, on_foot=on_foot)
            case WingJoined(others=others):
                return replace(now, wing=others)
            case WingAdded(name=name):
                return now if name in now.wing else replace(now, wing=(*now.wing, name))
            case WingLeft():
                return replace(now, wing=())
            case GameClosed():
                return replace(now, game_running=False, wing=())
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(fact)

    def _named(self, ship: Ship) -> Ship:
        """The ship, with its type's name in the game's language when it was ever seen."""
        key = ship.symbol.lower()
        if ship.type_name:
            self._type_names[key] = ship.type_name
            return ship
        return replace(ship, type_name=self._type_names.get(key))
