from edrockmaster.application.community_goals_service import CommunityGoalsService
from edrockmaster.domain.community_goals.goals import CommunityGoalsChanged
from tests.journal_entries import community_goal_entry, timestamp


def test_community_goals_follow_the_journal() -> None:
    service = CommunityGoalsService()
    [changed] = service.handle_journal_entry(community_goal_entry(0))
    assert isinstance(changed, CommunityGoalsChanged)
    assert service.goals[0].title == "Defend the Sirius Gate"
    reward = {"timestamp": timestamp(5), "event": "CommunityGoalReward", "CGID": 812}
    assert service.handle_journal_entry(reward) == [CommunityGoalsChanged(())]
    assert service.goals == ()


def test_other_entries_are_ignored() -> None:
    assert CommunityGoalsService().handle_journal_entry({"event": "Music"}) == []
