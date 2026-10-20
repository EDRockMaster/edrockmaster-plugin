"""Test doubles shared by several test modules."""

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime

from edrockmaster.application.community import Answer, Failed, Source, Unavailable
from edrockmaster.application.settings import DEFAULT_SETTINGS, PluginSettings
from edrockmaster.domain.commodities import GalaxyPrices, MarketOffer, MarketQuery
from edrockmaster.domain.engineering.goals import Goal, GoalId
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.mining.limpets import LimpetAlertRaised
from edrockmaster.domain.mining.prospecting import ProspectorAlertRaised
from edrockmaster.domain.situation.route import RouteAlertRaised


class FakeConfig:
    """Stands for EDMC's ``config``.

    Stricter than EDMC 6.1, whose getters never raise: a type mismatch raises
    ``ValueError`` here, as older config back-ends did, so that both behaviours
    are covered.
    """

    def __init__(self, values: dict[str, object] | None = None) -> None:
        self.values: dict[str, object] = dict(values or {})

    def get_str(self, key: str, *, default: str | None = None) -> str | None:
        value = self.values.get(key, default)
        if value is not None and not isinstance(value, str):
            raise ValueError(key)
        return value

    def get_bool(self, key: str, *, default: bool | None = None) -> bool:
        value = self.values.get(key, default)
        if not isinstance(value, bool):
            raise ValueError(key)
        return value

    def set(self, key: str, value: str | bool) -> None:
        self.values[key] = value


class FakeSettingsStore:
    def __init__(self, settings: PluginSettings = DEFAULT_SETTINGS) -> None:
        self.stored = settings
        self.saves = 0

    def load(self) -> PluginSettings:
        return self.stored

    def save(self, settings: PluginSettings) -> None:
        self.stored = settings
        self.saves += 1


class FakeNotifier:
    def __init__(self) -> None:
        self.notified: list[ProspectorAlertRaised | LimpetAlertRaised | RouteAlertRaised] = []

    def notify(self, alert: ProspectorAlertRaised | LimpetAlertRaised | RouteAlertRaised) -> None:
        self.notified.append(alert)


class FakeRecorder:
    def __init__(self) -> None:
        self.recorded: list[tuple[Entry, bool]] = []

    def record(self, entry: Entry, is_beta: bool) -> None:
        self.recorded.append((entry, is_beta))


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


class FakeGoalRepository:
    """Goals kept in memory; ``load`` answers at once (on the caller's thread)."""

    def __init__(self, stored: Sequence[Goal] = ()) -> None:
        self.stored: list[Goal] = list(stored)

    def load(self, on_loaded: Callable[[tuple[Goal, ...]], None]) -> None:
        on_loaded(tuple(self.stored))

    def add(self, goal: Goal) -> None:
        self.stored.append(goal)

    def replace(self, goal: Goal) -> None:
        self.stored = [goal if current.id == goal.id else current for current in self.stored]

    def remove(self, goal_id: GoalId) -> None:
        self.stored = [goal for goal in self.stored if goal.id != goal_id]

    def reorder(self, order: Sequence[GoalId]) -> None:
        by_id = {goal.id: goal for goal in self.stored}
        self.stored = [by_id[goal_id] for goal_id in order if goal_id in by_id]


NO_PRICES = Failed(Source.ARDENT, Unavailable.DOWN)


class FakeMarkets:
    """Answers each commodity's offers, and the galaxy's prices, as given."""

    def __init__(
        self,
        answers: dict[str, Answer[tuple[MarketOffer, ...]]],
        prices: Answer[Mapping[str, GalaxyPrices]] = NO_PRICES,
    ) -> None:
        self.answers = answers
        self.prices = prices
        self.asked: list[MarketQuery] = []
        self.prices_asked: list[bool] = []
        """Whether each request for the prices skipped the cache."""

    def find_offers(
        self,
        query: MarketQuery,
        on_answer: Callable[[Answer[tuple[MarketOffer, ...]]], None],
        *,
        refresh: bool = False,
    ) -> None:
        self.asked.append(query)
        on_answer(self.answers[query.commodity])

    def find_prices(
        self,
        on_answer: Callable[[Answer[Mapping[str, GalaxyPrices]]], None],
        *,
        refresh: bool = False,
    ) -> None:
        self.prices_asked.append(refresh)
        on_answer(self.prices)
