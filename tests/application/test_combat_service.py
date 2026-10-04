from datetime import timedelta

import pytest

from edrockmaster.application.hunting_service import HuntingService
from edrockmaster.domain.bounty.hunting import (
    CommunityGoalsChanged,
    HuntEnded,
    HuntEndReason,
    HuntStarted,
    HuntUpdated,
    VouchersUpdated,
)
from edrockmaster.domain.journal_reading import Entry
from tests.fakes import FixedClock
from tests.journal_entries import (
    T0,
    bounty_entry,
    community_goal_entry,
    redeem_entry,
    refined_entry,
    timestamp,
)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(T0 + timedelta(hours=1))


@pytest.fixture
def service(clock: FixedClock) -> HuntingService:
    return HuntingService(clock)


def test_kills_start_and_update_a_hunting_session(service: HuntingService) -> None:
    notifications = service.handle_journal_entry(bounty_entry(0, 120_000))
    assert [type(n) for n in notifications] == [HuntStarted, HuntUpdated, VouchersUpdated]
    stats = service.current_stats
    assert stats is not None
    assert (stats.kills, stats.bounty_credits) == (1, 120_000)


def test_other_entries_are_ignored(service: HuntingService) -> None:
    assert service.handle_journal_entry(refined_entry(0)) == []
    malformed: Entry = {"timestamp": timestamp(0), "event": "Bounty"}
    assert service.handle_journal_entry(malformed) == []


def test_redeemed_vouchers(service: HuntingService) -> None:
    service.handle_journal_entry(bounty_entry(0, 120_000))
    [updated] = service.handle_journal_entry(redeem_entry(5, 120_000))
    assert isinstance(updated, VouchersUpdated)
    assert service.vouchers.total == 0


def test_community_goals(service: HuntingService) -> None:
    [changed] = service.handle_journal_entry(community_goal_entry(0))
    assert isinstance(changed, CommunityGoalsChanged)
    assert service.community_goals[0].title == "Defend the Sirius Gate"


def test_reset_ends_the_session_at_the_current_time(
    service: HuntingService, clock: FixedClock
) -> None:
    assert service.reset_session() == []
    service.handle_journal_entry(bounty_entry(0))
    [ended] = service.reset_session()
    assert isinstance(ended, HuntEnded)
    assert (ended.at, ended.reason) == (clock.current, HuntEndReason.MANUAL)
    assert service.current_stats is None
