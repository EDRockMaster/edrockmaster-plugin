"""The reservation along the priority (ADR 0033), on hand-made goals and reserves."""

from datetime import UTC, datetime

from edrockmaster.domain.engineering.goals import BlueprintGoal, GoalId, ModificationGoal
from edrockmaster.domain.engineering.progress import GoalProgress
from edrockmaster.domain.engineering.reservation import reserve

T0 = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


def ship(name: str, **needed: int) -> GoalProgress:
    goal = BlueprintGoal(GoalId(name), "FSD_LongRange", "fsd", grade=5)
    return GoalProgress(goal, needed, {}, ())


def on_foot(name: str, **needed: int) -> GoalProgress:
    goal = ModificationGoal(GoalId(name), "tacticalsuit", "suit_backpackcapacity", T0)
    return GoalProgress(goal, needed, {}, ())


def by_name(reserved: tuple[GoalProgress, ...]) -> dict[str, GoalProgress]:
    return {progress.goal.id.value: progress for progress in reserved}


def test_the_first_goal_takes_its_share_and_the_next_lacks_it() -> None:
    goals = by_name(
        reserve([ship("first", arsenic=3), ship("second", arsenic=3)], {"arsenic": 4}, {})
    )
    assert goals["first"].missing == {}
    assert goals["first"].ready
    assert goals["first"].ready_alone
    assert goals["second"].missing == {"arsenic": 2}
    # Ready alone, not after the goal above it
    assert not goals["second"].ready
    assert goals["second"].ready_alone


def test_a_goal_that_cannot_be_completed_still_takes_what_it_needs() -> None:
    goals = by_name(
        reserve([ship("big", arsenic=10), ship("small", arsenic=1)], {"arsenic": 5}, {})
    )
    assert goals["big"].missing == {"arsenic": 5}
    assert goals["small"].missing == {"arsenic": 1}


def test_the_ship_and_on_foot_reserves_are_apart() -> None:
    reserved = reserve(
        [ship("ship", graphene=2), on_foot("foot", graphene=2)], {"graphene": 2}, {"graphene": 2}
    )
    assert all(progress.ready for progress in reserved)


def test_a_goal_that_counts_nothing_takes_nothing() -> None:
    unknown = GoalProgress(ship("unknown").goal, {"arsenic": 4}, None, ())
    not_counted = GoalProgress(on_foot("referral").goal, {"graphene": 2}, {}, (), counted=False)
    reserved = by_name(
        reserve(
            [unknown, not_counted, ship("after", arsenic=4), on_foot("foot", graphene=2)],
            {"arsenic": 4},
            {"graphene": 2},
        )
    )
    assert reserved["unknown"] is unknown
    assert reserved["referral"] is not_counted
    assert reserved["after"].ready
    assert reserved["foot"].ready


def test_the_priority_order_is_kept_and_the_reserves_untouched() -> None:
    held = {"arsenic": 4}
    reserved = reserve([ship("b", arsenic=1), ship("a", arsenic=1)], held, {})
    assert [progress.goal.id.value for progress in reserved] == ["b", "a"]
    assert held == {"arsenic": 4}
