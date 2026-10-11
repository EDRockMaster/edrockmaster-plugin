from datetime import UTC, datetime

import pytest

from edrockmaster.domain.community_goals.journal import (
    CommunityGoal,
    CommunityGoalLeft,
    CommunityGoalsUpdated,
    parse_entry,
)

TS = "2026-10-03T21:00:00Z"
AT = datetime(2026, 10, 3, 21, 0, tzinfo=UTC)


def test_community_goals_are_parsed() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "CommunityGoal",
            "CurrentGoals": [
                {
                    "CGID": 812,
                    "Title": "Defend the Sirius Gate",
                    "SystemName": "Sirius",
                    "MarketName": "Patterson Enterprise",
                    "Expiry": "2026-10-08T06:00:00Z",
                    "IsComplete": False,
                    "CurrentTotal": 9876543210,
                    "PlayerContribution": 25000000,
                    "NumContributors": 4321,
                    "TopTier": {"Name": "Tier 8", "Bonus": ""},
                    "TopRankSize": 10,
                    "PlayerInTopRank": False,
                    "TierReached": "Tier 4",
                    "PlayerPercentileBand": 25,
                    "Bonus": 0,
                }
            ],
        }
    )
    assert fact == CommunityGoalsUpdated(
        at=AT,
        goals=(
            CommunityGoal(
                cgid=812,
                title="Defend the Sirius Gate",
                system="Sirius",
                expiry=datetime(2026, 10, 8, 6, 0, tzinfo=UTC),
                complete=False,
                contribution=25000000,
                percentile_band=25,
                tier_reached="Tier 4",
                top_tier="Tier 8",
            ),
        ),
    )


def test_a_goal_with_little_known_is_parsed() -> None:
    fact = parse_entry(
        {"timestamp": TS, "event": "CommunityGoal", "CurrentGoals": [{"CGID": 1, "Title": "x"}]}
    )
    assert fact == CommunityGoalsUpdated(
        AT, (CommunityGoal(1, "x", None, None, False, 0, None, None, None),)
    )


@pytest.mark.parametrize("event", ["CommunityGoalReward", "CommunityGoalDiscard"])
def test_leaving_a_community_goal_is_parsed(event: str) -> None:
    # The game writes no new CommunityGoal once the reward is collected or the goal discarded
    entry = {
        "timestamp": TS,
        "event": event,
        "CGID": 861,
        "Name": "Brewer Corporation Hyperspace Satellite Launch",
        "System": "HIP 74116",
        "Reward": 200000000,
    }
    assert parse_entry(entry) == CommunityGoalLeft(AT, cgid=861)


@pytest.mark.parametrize(
    "entry",
    [
        {"timestamp": TS, "event": "CommunityGoal", "CurrentGoals": [{"Title": "x"}]},
        {
            "timestamp": TS,
            "event": "CommunityGoal",
            "CurrentGoals": [{"CGID": 1, "Title": "x", "Expiry": "soon"}],
        },
        {"timestamp": TS, "event": "CommunityGoalReward", "Name": "x"},
        {"timestamp": TS, "event": "CommunityGoalJoin", "CGID": 1, "Name": "x"},
        {"timestamp": TS, "event": "Bounty", "TotalReward": 1},
    ],
)
def test_irrelevant_or_malformed_entries_are_ignored(entry: dict[str, object]) -> None:
    assert parse_entry(entry) is None
