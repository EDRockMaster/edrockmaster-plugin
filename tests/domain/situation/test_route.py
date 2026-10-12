"""The current route and its alerts (ADR 0043), on the journal lines of a real route.

The lines are those written on 12 October 2026 from 78 Ursae Majoris, cut to five stops.
"""

from typing import Any

import pytest

from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.situation.journal import RouteStop, parse_entry
from edrockmaster.domain.situation.route import (
    CurrentRoute,
    Danger,
    JumpDiverted,
    RouteAlert,
    RouteAlertRaised,
    danger,
    scoopable,
)
from edrockmaster.domain.situation.situation import SituationTracker

TS = "2026-10-12T10:51:53Z"


def stop(system: str, star_class: str) -> dict[str, Any]:
    return {"StarSystem": system, "SystemAddress": 1, "StarPos": [0, 0, 0], "StarClass": star_class}


ROUTE = [
    stop("78 Ursae Majoris", "F"),
    stop("Zosi", "M"),
    stop("WISE 1405+5534", "Y"),
    stop("Sirius", "A"),
    stop("Sol", "G"),
]


def plotted(route: list[dict[str, Any]] | None = ROUTE) -> Entry:
    return {"event": "NavRoute", **({"Route": route} if route is not None else {})}


def targeted(system: str, star_class: str, left: int | None) -> Entry:
    fields = {"RemainingJumpsInRoute": left} if left is not None else {}
    return {"event": "FSDTarget", "Name": system, "StarClass": star_class, **fields}


def started(system: str, star_class: str) -> Entry:
    return {
        "event": "StartJump",
        "JumpType": "Hyperspace",
        "StarSystem": system,
        "StarClass": star_class,
    }


def jumped(system: str, fuel: float = 26.8, used: float = 5.2) -> Entry:
    return {"event": "FSDJump", "StarSystem": system, "FuelLevel": fuel, "FuelUsed": used}


class Flight:
    def __init__(self) -> None:
        self.tracker = SituationTracker()
        self.events: list[object] = []

    def __call__(self, *entries: Entry) -> "Flight":
        for raw in entries:
            fact = parse_entry({"timestamp": TS, **raw})
            if fact is not None:
                self.events += self.tracker.handle(fact)
        return self

    @property
    def route(self) -> CurrentRoute | None:
        return self.tracker.situation.route

    def alerts(self) -> list[tuple[RouteAlert, str]]:
        return [(e.alert, e.system) for e in self.events if isinstance(e, RouteAlertRaised)]

    def diverted(self) -> list[JumpDiverted]:
        return [e for e in self.events if isinstance(e, JumpDiverted)]


@pytest.mark.parametrize(
    ("star_class", "fuel", "kind"),
    [
        ("K", True, None),
        ("M", True, None),
        ("K_OrangeGiant", True, None),
        ("A_BlueWhiteSuperGiant", True, None),
        ("TTS", False, None),
        ("Y", False, None),
        ("L", False, None),
        ("AeBe", False, None),
        ("MS", False, None),
        ("DA", False, Danger.WHITE_DWARF),
        ("DQ", False, Danger.WHITE_DWARF),
        ("N", False, Danger.NEUTRON_STAR),
        ("H", False, Danger.BLACK_HOLE),
        ("SupermassiveBlackHole", False, Danger.BLACK_HOLE),
    ],
)
def test_the_stars(star_class: str, fuel: bool, kind: Danger | None) -> None:
    assert scoopable(star_class) is fuel
    assert danger(star_class) is kind


def test_a_plotted_route_and_its_next_jump() -> None:
    flight = Flight()(plotted(), targeted("Zosi", "M", 4))
    route = flight.route
    assert route is not None
    assert (route.destination, route.jumps_left, route.position) == ("Sol", 4, 0)
    assert route.next == RouteStop("Zosi", "M")
    assert flight.alerts() == []


def test_each_arrival_moves_the_route_on() -> None:
    # As written live: StartJump, then FSDTarget during the jump, then FSDJump
    flight = Flight()(plotted(), targeted("Zosi", "M", 4))
    flight(started("Zosi", "M"), targeted("WISE 1405+5534", "Y", 3), jumped("Zosi"))
    route = flight.route
    assert route is not None
    assert (route.position, route.jumps_left, route.next) == (
        1,
        3,
        RouteStop("WISE 1405+5534", "Y"),
    )
    assert route.next_scoopable_in == 2  # WISE is a brown dwarf: Sirius after it
    assert flight.diverted() == []


def test_the_game_clears_the_route_during_the_last_jump() -> None:
    flight = Flight()(plotted(ROUTE[3:]), targeted("Sol", "G", 1), started("Sol", "G"))
    flight({"event": "NavRouteClear"}, jumped("Sol"))
    assert flight.route is None
    assert flight.diverted() == []


def test_arriving_at_the_destination_ends_the_route() -> None:
    flight = Flight()(plotted(ROUTE[3:]), started("Sol", "G"), jumped("Sol"))
    assert flight.route is None


def test_a_jump_that_ends_elsewhere_leaves_the_route() -> None:
    flight = Flight()(plotted(), started("Zosi", "M"), jumped("Somewhere"))
    route = flight.route
    assert route is not None
    assert (route.off_route, route.next, route.destination) == (True, None, "Sol")
    [diverted] = flight.diverted()
    assert (diverted.aimed, diverted.reached) == ("Zosi", "Somewhere")
    # The game aims at a stop of the route again
    flight(targeted("Sirius", "A", 2))
    route = flight.route
    assert route is not None
    assert (route.off_route, route.position, route.next) == (False, 2, RouteStop("Sirius", "A"))


def test_a_jump_without_an_arrival_is_noted() -> None:
    flight = Flight()(plotted(), started("Zosi", "M"), started("Zosi", "M"))
    [diverted] = flight.diverted()
    assert (diverted.aimed, diverted.reached) == ("Zosi", None)
    route = flight.route
    assert route is not None
    assert route.position == 0  # only an arrival moves the route on


def test_supercruise_does_not_move_the_route() -> None:
    supercruise = {"event": "SupercruiseExit", "StarSystem": "Zosi"}
    flight = Flight()(plotted(), supercruise)
    route = flight.route
    assert route is not None
    assert route.position == 0


def test_a_restart_on_the_route_finds_its_place() -> None:
    flight = Flight()(plotted(), {"event": "Location", "StarSystem": "Zosi"})
    route = flight.route
    assert route is not None
    assert (route.position, route.next) == (1, RouteStop("WISE 1405+5534", "Y"))


def test_without_the_list_the_route_comes_from_the_next_jump() -> None:
    # A NavRoute line read again at start: NavRoute.json described a later one
    flight = Flight()(plotted(None))
    route = flight.route
    assert route is not None
    assert (route.destination, route.next, route.off_route) == (None, None, False)
    flight(targeted("Zosi", "M", 2))
    route = flight.route
    assert route is not None
    assert (route.next, route.jumps_left, route.next_scoopable_in) == (
        RouteStop("Zosi", "M"),
        2,
        None,
    )
    flight(jumped("Zosi"))
    route = flight.route
    assert route is not None
    assert (route.next, route.jumps_left) == (None, 1)
    flight(targeted("Sol", "G", 1), jumped("Sol"))
    assert flight.route is None


def test_an_fsd_target_alone_starts_a_route_with_its_jumps() -> None:
    assert Flight()(targeted("Zosi", "M", None)).route is None
    route = Flight()(targeted("Zosi", "M", 3)).route
    assert route is not None
    assert (route.next, route.jumps_left, route.stops) == (RouteStop("Zosi", "M"), 3, ())


@pytest.mark.parametrize(
    "route",
    [[stop("Sol", "G")], [stop("Sol", "G"), {"StarSystem": "Zosi"}], "not a list"],
)
def test_an_odd_route_file(route: Any) -> None:
    flight = Flight()(plotted(route))
    current = flight.route
    if route and isinstance(route, list) and len(route) == 1:
        assert current is None  # already there
    else:
        assert current is not None
        assert current.stops == ()


def test_a_dangerous_star_ahead_alerts_once() -> None:
    dwarf = [stop("Sol", "G"), stop("Sirius B", "DA"), stop("Procyon", "F")]
    flight = Flight()(plotted(dwarf), targeted("Sirius B", "DA", 2), targeted("Sirius B", "DA", 2))
    route = flight.route
    assert route is not None
    assert route.danger is Danger.WHITE_DWARF
    assert flight.alerts() == [(RouteAlert.DANGEROUS_STAR, "Sirius B")]


def test_fuel_tight_before_the_next_scoopable_star() -> None:
    dry = [
        stop("A", "G"),
        stop("B", "G"),
        stop("C", "Y"),
        stop("D", "L"),
        stop("E", "T"),
        stop("F", "K"),
    ]
    flight = Flight()(plotted(dry), started("B", "G"), jumped("B", fuel=12.0, used=5.0))
    route = flight.route
    assert route is not None
    assert route.next_scoopable_in == 4  # C, D, E, then F
    assert route.fuel_tight  # 4 jumps of 5 t, 12 t left
    assert flight.alerts() == [(RouteAlert.FUEL_TIGHT, "C")]
    flight({"event": "FuelScoop", "Scooped": 10.0, "Total": 22.0})
    route = flight.route
    assert route is not None
    assert route.fuel_level == 22.0
    assert not route.fuel_tight


def test_no_fuel_alert_before_the_first_jump() -> None:
    flight = Flight()(plotted([stop("A", "G"), stop("C", "Y"), stop("F", "K")]))
    route = flight.route
    assert route is not None
    assert not route.fuel_tight
    assert flight.alerts() == []


def test_no_fuel_alert_without_a_scoopable_star_ahead() -> None:
    # Nothing to reach: the alert would only say "never"
    flight = Flight()(plotted([stop("A", "G"), stop("B", "G"), stop("C", "Y"), stop("D", "L")]))
    flight(started("B", "G"), jumped("B", fuel=1.0, used=5.0))
    route = flight.route
    assert route is not None
    assert (route.next_scoopable_in, route.fuel_tight) == (None, False)


def test_the_fuel_is_known_before_the_route() -> None:
    flight = Flight()({"event": "FuelScoop", "Scooped": 1.5, "Total": 30.5}, plotted())
    route = flight.route
    assert route is not None
    assert route.fuel_level == 30.5


def test_a_fuel_scoop_without_its_total_is_ignored() -> None:
    assert parse_entry({"timestamp": TS, "event": "FuelScoop", "Scooped": 1.5}) is None


def test_a_jump_back_where_it_left_puts_the_route_back_there() -> None:
    # As a Thargoid hyperdiction is said to do: aimed at Zosi, back in 78 Ursae Majoris
    flight = Flight()({"event": "Location", "StarSystem": "78 Ursae Majoris"}, plotted())
    flight(targeted("Zosi", "M", 4), started("Zosi", "M"), jumped("78 Ursae Majoris"))
    route = flight.route
    assert route is not None
    assert (route.position, route.next, route.jumps_left, route.off_route) == (
        0,
        RouteStop("Zosi", "M"),
        4,
        False,
    )
    [diverted] = flight.diverted()
    assert (diverted.aimed, diverted.reached, diverted.back) == ("Zosi", "78 Ursae Majoris", True)


def test_supercruise_tells_where_the_jump_left() -> None:
    supercruise = {"event": "SupercruiseEntry", "StarSystem": "78 Ursae Majoris"}
    flight = Flight()(supercruise, plotted(), started("Zosi", "M"), jumped("Somewhere"))
    [diverted] = flight.diverted()
    assert not diverted.back
