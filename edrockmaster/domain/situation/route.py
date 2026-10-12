"""The route the commander plotted, and the stars ahead of them (ADR 0043).

``RouteTracker`` follows the route from the journal: ``NavRoute`` with the list
the journal reader adds from ``NavRoute.json``, ``FSDTarget`` for the next jump,
the arrivals for the commander's place in the list. Only an arrival moves the
route on; one off the list leaves the destination but no next jump, until the
game targets one again; one back in a system of the list (the one the jump
left, after a hyperdiction) puts the route back there. The game clears the
route itself during the last jump.

It raises an alert, once per jump aimed at, when the next star is dangerous on
arrival (a white dwarf, a neutron star, a black hole), and when the fuel left
does not reach the next star where fuel can be scooped, estimated on the most
one jump of the route used.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import assert_never

from edrockmaster.domain.situation.journal import (
    FuelScooped,
    JumpStarted,
    JumpTargeted,
    Located,
    RouteCleared,
    RoutePlotted,
    RouteStop,
    SystemReached,
)

_SCOOPABLE = frozenset("OBAFGKM")
_BLACK_HOLES = frozenset({"H", "SupermassiveBlackHole"})


class Danger(Enum):
    WHITE_DWARF = "whiteDwarf"
    NEUTRON_STAR = "neutronStar"
    BLACK_HOLE = "blackHole"


def scoopable(star_class: str) -> bool:
    """Fuel can be scooped there: O, B, A, F, G, K, M, their giants and supergiants included
    (``K_OrangeGiant``)."""
    return star_class.split("_", maxsplit=1)[0] in _SCOOPABLE


def danger(star_class: str) -> Danger | None:
    if star_class in _BLACK_HOLES:
        return Danger.BLACK_HOLE
    if star_class == "N":
        return Danger.NEUTRON_STAR
    if star_class.startswith("D"):  # D, DA, DAB, DQ, DC…
        return Danger.WHITE_DWARF
    return None


@dataclass(frozen=True, slots=True)
class CurrentRoute:
    stops: tuple[RouteStop, ...]
    """From the starting system to the destination; empty when the list is not known."""
    position: int | None
    """The commander's place in ``stops``; ``None`` when unknown or off the route."""
    next: RouteStop | None
    jumps_left: int | None
    off_route: bool = False
    fuel_level: float | None = None
    jump_fuel: float = 0.0
    """The most fuel one jump of this route used: nothing before the first."""

    @property
    def destination(self) -> str | None:
        return self.stops[-1].system if self.stops else None

    @property
    def next_scoopable_in(self) -> int | None:
        """Jumps to the next star where fuel can be scooped; ``None`` if none is known ahead."""
        if self.position is None:
            return None
        ahead = self.stops[self.position + 1 :]
        return next((i + 1 for i, stop in enumerate(ahead) if scoopable(stop.star_class)), None)

    @property
    def danger(self) -> Danger | None:
        return danger(self.next.star_class) if self.next else None

    @property
    def fuel_tight(self) -> bool:
        if self.next is None or scoopable(self.next.star_class) or self.fuel_level is None:
            return False
        jumps = self.next_scoopable_in
        if jumps is None or not self.jump_fuel:
            return False
        return jumps * self.jump_fuel > self.fuel_level


class RouteAlert(Enum):
    DANGEROUS_STAR = "dangerousStar"
    FUEL_TIGHT = "fuelTight"


@dataclass(frozen=True, slots=True)
class RouteAlertRaised:
    at: datetime
    alert: RouteAlert
    system: str
    """The jump aimed at."""


@dataclass(frozen=True, slots=True)
class JumpDiverted:
    """A hyperspace jump that did not arrive where it aimed: written to the application's log,
    to survey the journal the day it happens (a Thargoid hyperdiction, for one)."""

    at: datetime
    aimed: str
    reached: str | None
    """``None``: another jump began before any arrival."""
    back: bool = False
    """Back in the system the jump left: what a Thargoid hyperdiction is said to do (read on
    the web, never seen in the player's journals)."""


type RouteFact = (
    RoutePlotted | RouteCleared | JumpTargeted | JumpStarted | SystemReached | Located | FuelScooped
)
type RouteEvent = RouteAlertRaised | JumpDiverted


class RouteTracker:
    def __init__(self) -> None:
        self._route: CurrentRoute | None = None
        self._fuel: float | None = None
        self._aimed: str | None = None
        self._here: str | None = None
        """The commander's system, as far as the journal said."""
        self._left: str | None = None
        """The system the jump in progress left."""
        self._sounded: set[tuple[RouteAlert, str]] = set()

    @property
    def route(self) -> CurrentRoute | None:
        return self._route

    def handle(self, fact: RouteFact) -> list[RouteEvent]:  # noqa: PLR0912 - a case a fact
        events: list[RouteEvent] = []
        match fact:
            case RoutePlotted(stops=stops):
                self._sounded.clear()
                self._route = self._plotted(stops)
            case RouteCleared():
                self._sounded.clear()
                self._route = None
            case JumpTargeted():
                self._route = self._targeted(fact)
            case JumpStarted(at=at, stop=stop):
                if self._aimed is not None:
                    events.append(JumpDiverted(at, self._aimed, None))
                self._aimed, self._left = stop.system, self._here
            case SystemReached(arrival=False, system=system):
                self._here = system
                return []
            case SystemReached(at=at, system=system):
                if self._aimed is not None and self._aimed != system:
                    back = self._left is not None and self._left == system
                    events.append(JumpDiverted(at, self._aimed, system, back))
                self._aimed, self._here = None, system
                if fact.fuel_level is not None:
                    self._fuel = fact.fuel_level
                self._route = self._arrived(system, fact.fuel_used)
            case Located(system=system):
                self._aimed, self._here = None, system
                self._route = self._arrived(system, None)
            case FuelScooped(fuel_level=level):
                self._fuel = level
                if self._route is not None:
                    self._route = replace(self._route, fuel_level=level)
            case _:  # pragma: no cover - exhaustiveness checked by mypy
                assert_never(fact)
        return events + self._alerts(fact.at)

    def _plotted(self, stops: tuple[RouteStop, ...]) -> CurrentRoute | None:
        if len(stops) == 1:
            return None
        if not stops:
            return CurrentRoute((), None, None, None, fuel_level=self._fuel)
        return CurrentRoute(stops, 0, stops[1], len(stops) - 1, fuel_level=self._fuel)

    def _targeted(self, fact: JumpTargeted) -> CurrentRoute | None:
        route = self._route
        if fact.jumps_left is None:
            return route  # a single system aimed at: no route
        if route is None:
            return CurrentRoute((), None, fact.stop, fact.jumps_left, fuel_level=self._fuel)
        index = _index(route.stops, fact.stop.system)
        position = index - 1 if index else None
        return replace(
            route, next=fact.stop, jumps_left=fact.jumps_left, position=position, off_route=False
        )

    def _arrived(self, system: str, fuel_used: float | None) -> CurrentRoute | None:
        route = self._route
        if route is None:
            return None
        route = replace(
            route,
            fuel_level=self._fuel,
            jump_fuel=max(route.jump_fuel, fuel_used or 0.0),
        )
        if not route.stops:
            left = route.jumps_left - 1 if route.jumps_left is not None else None
            if left == 0:
                return None
            return replace(route, next=None, jumps_left=left)
        index = _index(route.stops, system)
        if index is None:
            return replace(route, position=None, next=None, off_route=True)
        if index == len(route.stops) - 1:
            return None
        return replace(
            route,
            position=index,
            next=route.stops[index + 1],
            jumps_left=len(route.stops) - 1 - index,
            off_route=False,
        )

    def _alerts(self, at: datetime) -> list[RouteEvent]:
        route = self._route
        if route is None or route.next is None:
            return []
        raised: list[RouteEvent] = []
        for alert, on in (
            (RouteAlert.DANGEROUS_STAR, route.danger is not None),
            (RouteAlert.FUEL_TIGHT, route.fuel_tight),
        ):
            key = (alert, route.next.system)
            if on and key not in self._sounded:
                self._sounded.add(key)
                raised.append(RouteAlertRaised(at, alert, route.next.system))
        return raised


def _index(stops: tuple[RouteStop, ...], system: str) -> int | None:
    return next((i for i, stop in enumerate(stops) if stop.system == system), None)
