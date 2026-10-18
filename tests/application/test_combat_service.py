from datetime import timedelta

import pytest

from edrockmaster.application.combat_service import CombatService
from edrockmaster.application.past_journals import PastJournalsRead
from edrockmaster.domain.combat.journal import BountyAwarded, FactionReward
from edrockmaster.domain.combat.session import (
    CombatEnded,
    CombatEndReason,
    CombatStarted,
    CombatUpdated,
)
from edrockmaster.domain.combat.vouchers import (
    NOT_READ_YET,
    PastJournals,
    VoucherLedger,
    VouchersUpdated,
)
from edrockmaster.domain.journal_reading import Entry
from tests.fakes import FixedClock
from tests.journal_entries import (
    T0,
    bounty_entry,
    redeem_entry,
    refined_entry,
    timestamp,
)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(T0 + timedelta(hours=1))


@pytest.fixture
def service(clock: FixedClock) -> CombatService:
    return CombatService(clock)


def test_kills_start_and_update_a_combat_session(service: CombatService) -> None:
    notifications = service.handle_journal_entry(bounty_entry(0, 120_000))
    assert [type(n) for n in notifications] == [CombatStarted, CombatUpdated, VouchersUpdated]
    stats = service.current_stats
    assert stats is not None
    assert (stats.kills, stats.bounty_credits) == (1, 120_000)


def test_other_entries_are_ignored(service: CombatService) -> None:
    assert service.handle_journal_entry(refined_entry(0)) == []  # mining: noted, no notification
    malformed: Entry = {"timestamp": timestamp(0), "event": "Bounty"}
    assert service.handle_journal_entry(malformed) == []


def test_redeemed_vouchers(service: CombatService) -> None:
    service.handle_journal_entry(bounty_entry(0, 120_000))
    [updated] = service.handle_journal_entry(redeem_entry(5, 120_000))
    assert isinstance(updated, VouchersUpdated)
    assert service.vouchers.total == 0


def test_reset_ends_the_session_at_the_current_time(
    service: CombatService, clock: FixedClock
) -> None:
    assert service.reset_session() == []
    service.handle_journal_entry(bounty_entry(0))
    [ended] = service.reset_session()
    assert isinstance(ended, CombatEnded)
    assert (ended.at, ended.reason) == (clock.current, CombatEndReason.MANUAL)
    assert service.current_stats is None


# --- vouchers of past game sessions (ADR 0052) ---------------------------------------------

DONE = PastJournals(read=2, total=2)
CURRENT = "Journal.2026-10-18T083109.01.log"
EARLIER = "Journal.2026-10-17T201901.01.log"


def past(*rewards: int, indexed: frozenset[str] = frozenset()) -> PastJournalsRead:
    ledger = VoucherLedger()
    for reward in rewards:
        ledger.apply(
            BountyAwarded(T0, reward, (FactionReward("Federation", reward),), None, None, False)
        )
    return PastJournalsRead(ledger, indexed, DONE)


def test_until_past_journals_are_read_the_vouchers_say_so(service: CombatService) -> None:
    *_, updated = service.handle_journal_entry(bounty_entry(0, 120_000))
    assert updated == VouchersUpdated(service.vouchers, NOT_READ_YET)
    assert not updated.past.complete


def test_vouchers_of_past_sessions_come_before_those_read_live(service: CombatService) -> None:
    service.journal_file_opened(CURRENT)
    service.handle_journal_entry(bounty_entry(0, 120_000))
    [updated] = service.past_journals_read(past(33_552_700))
    assert updated.past == DONE
    assert updated.vouchers.bounties == {"Federation": 33_672_700}
    assert service.past_journals == DONE


def test_a_redemption_read_live_pays_vouchers_of_past_sessions(service: CombatService) -> None:
    service.past_journals_read(past(33_552_700))
    [updated] = service.handle_journal_entry(redeem_entry(5, 20_000_000))
    assert isinstance(updated, VouchersUpdated)
    assert updated.vouchers.total == 0


def test_a_file_the_past_journals_count_is_not_counted_twice(service: CombatService) -> None:
    service.journal_file_opened(EARLIER)
    service.handle_journal_entry(bounty_entry(0, 100_000))
    service.journal_file_opened(CURRENT)
    service.handle_journal_entry(bounty_entry(1, 20_000))
    service.past_journals_read(past(100_000, indexed=frozenset({EARLIER})))
    assert service.vouchers.bounties == {"Federation": 120_000}
    service.past_journals_read(past(100_000, indexed=frozenset({EARLIER})))
    assert service.vouchers.bounties == {"Federation": 120_000}


def test_other_kills_than_vouchers_are_not_kept_for_later(service: CombatService) -> None:
    service.handle_journal_entry(refined_entry(0))
    assert service.past_journals_read(past())[0].vouchers.total == 0
