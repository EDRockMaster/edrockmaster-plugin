"""Engineer unlock goals (ADR 0027, ADR 0031)."""

from datetime import UTC, datetime

import pytest

from edrockmaster.domain.engineering.catalogue import OnFootKind
from edrockmaster.domain.engineering.events import EngineeringNotification, GoalDone, GoalReady
from edrockmaster.domain.engineering.goals import EngineerUnlockGoal, GoalId
from edrockmaster.domain.engineering.journal import (
    EngineerProgressed,
    EngineersStated,
    EngineerState,
    EngineerStatus,
)
from edrockmaster.domain.engineering.on_foot_journal import LockerStated, Stock
from edrockmaster.domain.engineering.progress import GoalProgress
from edrockmaster.domain.engineering.session import EngineeringTracker
from tests.domain.engineering.catalogue_data import catalogue

T0 = datetime(2026, 10, 11, 10, 0, tzinfo=UTC)
FARSEER = 300100
DOMINO = 400002
# The test catalogue: Kit Fowler is referred by Domino Green once given 5 chemical samples, and
# unlocked by selling 3 graphene; Felicity Farseer's conditions are text only
KIT = 400004
GOAL = EngineerUnlockGoal(GoalId("kit"), KIT)


def locker(**counts: int) -> LockerStated:
    kinds = {"graphene": OnFootKind.COMPONENT, "chemicalsample": OnFootKind.ITEM}
    return LockerStated(
        T0, tuple(Stock(symbol, kinds[symbol], count) for symbol, count in counts.items())
    )


def state(engineer_id: int, status: EngineerStatus) -> EngineerState:
    return EngineerState(engineer_id, f"engineer {engineer_id}", status)


def progress_of(tracker: EngineeringTracker) -> GoalProgress:
    [progress] = tracker.stats().goals
    return progress


def of(kind: type, notifications: list[EngineeringNotification]) -> list[object]:
    return [n for n in notifications if isinstance(n, kind)]


@pytest.fixture
def tracker() -> EngineeringTracker:
    return EngineeringTracker(catalogue())


def test_a_goal_names_its_engineer() -> None:
    assert GOAL.engineer_id == KIT
    with pytest.raises(ValueError, match="engineer"):
        EngineerUnlockGoal(GoalId("none"), 0)


def test_an_engineer_not_known_yet_takes_the_referral_and_the_unlock(
    tracker: EngineeringTracker,
) -> None:
    tracker.add_goal(GOAL)
    progress = progress_of(tracker)
    assert progress.needed == {"chemicalsample": 5, "graphene": 3}
    assert progress.counted
    assert progress.missing is None
    tracker.handle(locker(graphene=3, chemicalsample=1))
    assert progress_of(tracker).missing == {"chemicalsample": 4}
    notifications = tracker.handle(locker(graphene=3, chemicalsample=5))
    assert of(GoalReady, notifications) == [GoalReady(GOAL)]
    # Counted in the on-foot shopping list, not the ship's
    assert tracker.on_foot_shopping_list() == {}
    assert tracker.shopping_list() == {}


def test_once_known_the_unlock_alone(tracker: EngineeringTracker) -> None:
    tracker.add_goal(GOAL)
    tracker.handle(EngineersStated(T0, (state(KIT, EngineerStatus.INVITED),)))
    assert progress_of(tracker).needed == {"graphene": 3}
    tracker.handle(locker(graphene=1))
    assert tracker.on_foot_shopping_list() == {"graphene": 2}


def test_the_goal_is_done_once_the_engineer_is_unlocked(tracker: EngineeringTracker) -> None:
    tracker.add_goal(GOAL)
    tracker.add_goal(EngineerUnlockGoal(GoalId("farseer"), FARSEER))
    unlocked = EngineerProgressed(T0, state(KIT, EngineerStatus.UNLOCKED))
    assert of(GoalDone, tracker.handle(unlocked)) == [GoalDone(GOAL)]
    stated = EngineersStated(T0, (state(FARSEER, EngineerStatus.UNLOCKED),))
    assert of(GoalDone, tracker.handle(stated)) == [
        GoalDone(EngineerUnlockGoal(GoalId("farseer"), FARSEER))
    ]
    assert tracker.goals == ()


def test_conditions_the_journal_cannot_count_keep_the_goal_from_being_ready(
    tracker: EngineeringTracker,
) -> None:
    # Felicity Farseer: a rank to reach, a commodity to deliver
    tracker.add_goal(EngineerUnlockGoal(GoalId("farseer"), FARSEER))
    tracker.handle(locker(graphene=9))
    progress = progress_of(tracker)
    assert progress.needed == {}
    assert not progress.counted
    assert not progress.ready


def test_a_barred_engineer_is_never_ready(tracker: EngineeringTracker) -> None:
    tracker.add_goal(GOAL)
    tracker.handle(EngineersStated(T0, (state(KIT, EngineerStatus.BARRED),)))
    tracker.handle(locker(graphene=3, chemicalsample=5))
    assert not progress_of(tracker).ready


def test_an_engineer_without_a_sheet(tracker: EngineeringTracker) -> None:
    tracker.add_goal(EngineerUnlockGoal(GoalId("who"), 300999))
    progress = progress_of(tracker)
    assert not progress.known
    assert not progress.ready
