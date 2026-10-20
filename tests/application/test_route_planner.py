"""Trade routes asked of a planner that answers at once (ADR 0057)."""

from collections.abc import Callable

from edrockmaster.application.community import Pending, Source
from edrockmaster.application.route_planner import RoutePlanner, RouteProgress
from edrockmaster.domain.trade.routes import RouteQuery

QUERY = RouteQuery("Sol", "Abraham Lincoln", cargo_capacity=720, credits=1_000_000)
PENDING = Pending(Source.SPANSH, "J")


class FakeRoutes:
    def __init__(self) -> None:
        self.asked: list[tuple[str, object]] = []

    def plan(
        self,
        query: RouteQuery,
        on_answer: Callable[[RouteProgress], None],
        *,
        refresh: bool = False,
    ) -> None:
        self.asked.append(("plan", refresh))
        on_answer(PENDING)

    def follow(
        self, query: RouteQuery, job: str, on_answer: Callable[[RouteProgress], None]
    ) -> None:
        self.asked.append(("follow", job))
        on_answer(PENDING)


def test_a_route_is_planned_then_followed() -> None:
    routes = FakeRoutes()
    planner = RoutePlanner(routes)
    answers: list[RouteProgress] = []
    planner.plan(QUERY, answers.append, refresh=True)
    planner.follow(QUERY, "J", answers.append)
    assert routes.asked == [("plan", True), ("follow", "J")]
    assert answers == [PENDING, PENDING]
