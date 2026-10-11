from datetime import UTC, datetime, timedelta

from edrockmaster.domain.community_goals.goals import CommunityGoals, CommunityGoalsChanged
from edrockmaster.domain.community_goals.journal import (
    CommunityGoal,
    CommunityGoalLeft,
    CommunityGoalsUpdated,
)

T0 = datetime(2026, 10, 11, 6, 36, tzinfo=UTC)


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def goal(cgid: int, *, complete: bool = False) -> CommunityGoal:
    return CommunityGoal(
        cgid=cgid,
        title=f"Goal {cgid}",
        system="HIP 74116",
        expiry=None,
        complete=complete,
        contribution=1_000,
        percentile_band=None,
        tier_reached=None,
        top_tier=None,
    )


def test_nothing_joined_at_first() -> None:
    assert CommunityGoals().goals == ()


def test_the_list_stated_is_kept_and_notified() -> None:
    goals = CommunityGoals()
    assert goals.handle(CommunityGoalsUpdated(at(0), (goal(812),))) == [
        CommunityGoalsChanged((goal(812),))
    ]
    assert goals.goals == (goal(812),)


def test_the_same_list_again_changes_nothing() -> None:
    # The game repeats the list every few minutes near a goal
    goals = CommunityGoals()
    goals.handle(CommunityGoalsUpdated(at(0), (goal(812),)))
    assert goals.handle(CommunityGoalsUpdated(at(10), (goal(812),))) == []


def test_a_goal_missing_from_a_new_list_goes() -> None:
    goals = CommunityGoals()
    goals.handle(CommunityGoalsUpdated(at(0), (goal(812), goal(861))))
    assert goals.handle(CommunityGoalsUpdated(at(10), (goal(812),))) == [
        CommunityGoalsChanged((goal(812),))
    ]


def test_a_goal_handed_in_goes_without_a_new_list() -> None:
    # As in the player's journal: complete at load, reward collected 3 h 38 min later
    goals = CommunityGoals()
    goals.handle(CommunityGoalsUpdated(at(0), (goal(812), goal(861, complete=True))))
    assert goals.handle(CommunityGoalLeft(at(218), cgid=861)) == [
        CommunityGoalsChanged((goal(812),))
    ]
    assert goals.goals == (goal(812),)


def test_leaving_an_unknown_goal_changes_nothing() -> None:
    goals = CommunityGoals()
    goals.handle(CommunityGoalsUpdated(at(0), (goal(812),)))
    assert goals.handle(CommunityGoalLeft(at(5), cgid=999)) == []
    assert goals.goals == (goal(812),)
