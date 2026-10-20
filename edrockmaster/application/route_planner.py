"""Trade routes (ADR 0047, ADR 0057), on a community source that computes them as jobs: the
interface follows the job, one request at a time, and no thread waits for it."""

from __future__ import annotations

from collections.abc import Callable

from edrockmaster.application.community import Answer, Pending
from edrockmaster.application.ports import TradeRoutes
from edrockmaster.domain.trade.routes import RouteQuery, TradeRoute

type RouteProgress = Answer[TradeRoute] | Pending


class RoutePlanner:
    def __init__(self, routes: TradeRoutes) -> None:
        self._routes = routes

    def plan(
        self,
        query: RouteQuery,
        on_answer: Callable[[RouteProgress], None],
        *,
        refresh: bool = False,
    ) -> None:
        self._routes.plan(query, on_answer, refresh=refresh)

    def follow(
        self, query: RouteQuery, job: str, on_answer: Callable[[RouteProgress], None]
    ) -> None:
        self._routes.follow(query, job, on_answer)
