from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.journal import (
    AsteroidCracked,
    AsteroidProspected,
    CargoChanged,
    CargoEjected,
    CommodityRefined,
    CommoditySold,
    ContentLevel,
    GameLoaded,
    LeaveReason,
    LimpetKind,
    LimpetLaunched,
    MaterialShare,
    MiningAreaLeft,
    RingEntered,
)
from edrockmaster.domain.session import (
    IDLE_THRESHOLD,
    EndReason,
    MiningTracker,
    SaleRecorded,
    SessionEnded,
    SessionNotification,
    SessionStarted,
    SessionUpdated,
)

T0 = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
PAINITE = Commodity.from_symbol("painite")
PLATINUM = Commodity.from_symbol("platinum")


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def ring(minutes: float = 0) -> RingEntered:
    return RingEntered(at=at(minutes), system="Col 285", system_address=42, ring="Col 285 2 A Ring")


def refined(minutes: float, commodity: Commodity = PAINITE) -> CommodityRefined:
    return CommodityRefined(at=at(minutes), commodity=commodity)


def prospected(
    minutes: float,
    content: ContentLevel = ContentLevel.HIGH,
    motherlode: Commodity | None = None,
) -> AsteroidProspected:
    return AsteroidProspected(
        at=at(minutes),
        materials=(MaterialShare(PAINITE, 30.0),),
        content=content,
        remaining=100.0,
        motherlode=motherlode,
    )


def launched(minutes: float, kind: LimpetKind) -> LimpetLaunched:
    return LimpetLaunched(at=at(minutes), kind=kind)


# --- lifecycle ----------------------------------------------------------------------------


def test_no_session_before_any_mining_activity() -> None:
    tracker = MiningTracker()
    assert tracker.handle(ring()) == []
    assert tracker.session is None


@pytest.mark.parametrize(
    "first_activity",
    [
        launched(1, LimpetKind.PROSPECTOR),
        prospected(1),
        refined(1),
        AsteroidCracked(at=at(1)),
    ],
)
def test_first_mining_activity_starts_a_session(first_activity: object) -> None:
    tracker = MiningTracker()
    tracker.handle(ring())
    notifications = tracker.handle(first_activity)  # type: ignore[arg-type]
    assert isinstance(notifications[0], SessionStarted)
    assert notifications[0].ring == "Col 285 2 A Ring"
    assert notifications[0].system == "Col 285"
    assert tracker.session is not None
    assert tracker.session.started_at == at(1)


def test_the_first_activity_is_counted_and_notified_with_the_start() -> None:
    started, updated = MiningTracker().handle(refined(1))
    assert isinstance(started, SessionStarted)
    assert isinstance(updated, SessionUpdated)
    assert updated.stats.total_tons == 1


def test_non_mining_limpet_does_not_start_a_session() -> None:
    tracker = MiningTracker()
    assert tracker.handle(launched(1, LimpetKind.OTHER)) == []
    assert tracker.session is None


def test_cargo_changes_alone_do_not_start_a_session() -> None:
    tracker = MiningTracker()
    cargo = CargoChanged(at=at(1), total=4, inventory=((PAINITE, 4),))
    assert tracker.handle(cargo) == []
    assert tracker.session is None


def test_session_can_start_without_a_known_ring() -> None:
    # e.g. EDMC started while the player was already in the ring
    tracker = MiningTracker()
    started = tracker.handle(refined(1))[0]
    assert isinstance(started, SessionStarted)
    assert started.ring is None


@pytest.mark.parametrize(
    ("reason", "end"),
    [
        (LeaveReason.SUPERCRUISE, EndReason.SUPERCRUISE),
        (LeaveReason.JUMP, EndReason.JUMP),
        (LeaveReason.DOCKED, EndReason.DOCKED),
        (LeaveReason.GAME_CLOSED, EndReason.GAME_CLOSED),
    ],
)
def test_leaving_the_area_ends_the_session(reason: LeaveReason, end: EndReason) -> None:
    tracker = MiningTracker()
    tracker.handle(refined(1))
    notifications = tracker.handle(MiningAreaLeft(at=at(5), reason=reason))
    assert len(notifications) == 1
    ended = notifications[0]
    assert isinstance(ended, SessionEnded)
    assert ended.reason is end
    assert ended.stats.total_tons == 1
    assert tracker.session is None


def test_leaving_without_a_session_does_nothing() -> None:
    tracker = MiningTracker()
    assert tracker.handle(MiningAreaLeft(at=at(1), reason=LeaveReason.SUPERCRUISE)) == []


def test_manual_reset_ends_the_session_and_a_new_one_can_start() -> None:
    tracker = MiningTracker()
    tracker.handle(refined(1))
    ended = tracker.reset(at(2))
    assert isinstance(ended, SessionEnded)
    assert ended.reason is EndReason.MANUAL
    started = tracker.handle(refined(3))[0]
    assert isinstance(started, SessionStarted)
    assert tracker.session is not None
    assert tracker.session.stats.total_tons == 1


def test_manual_reset_without_a_session_returns_nothing() -> None:
    assert MiningTracker().reset(at(1)) is None


def test_the_ring_is_forgotten_after_leaving() -> None:
    tracker = MiningTracker()
    tracker.handle(ring())
    tracker.handle(refined(1))
    tracker.handle(MiningAreaLeft(at=at(2), reason=LeaveReason.SUPERCRUISE))
    started = tracker.handle(refined(3))[0]
    assert isinstance(started, SessionStarted)
    assert started.ring is None


# --- statistics ---------------------------------------------------------------------------


def test_every_mining_activity_updates_the_session() -> None:
    tracker = MiningTracker()
    tracker.handle(refined(1))
    notifications = tracker.handle(refined(2))
    assert len(notifications) == 1
    assert isinstance(notifications[0], SessionUpdated)
    assert notifications[0].stats.total_tons == 2


def test_tons_are_counted_per_commodity() -> None:
    tracker = MiningTracker()
    for minute, commodity in enumerate([PAINITE, PAINITE, PLATINUM], start=1):
        tracker.handle(refined(minute, commodity))
    assert tracker.session is not None
    stats = tracker.session.stats
    assert stats.tons_by_commodity == {PAINITE: 2, PLATINUM: 1}
    assert stats.total_tons == 3


def test_active_duration_and_tons_per_hour() -> None:
    tracker = MiningTracker()
    tracker.handle(refined(0))
    for minute in range(1, 31):  # one ton per minute for 30 minutes
        tracker.handle(refined(minute))
    assert tracker.session is not None
    stats = tracker.session.stats
    assert stats.active_duration == timedelta(minutes=30)
    assert stats.total_tons == 31
    assert stats.tons_per_hour == pytest.approx(62.0)


def test_idle_time_is_not_counted() -> None:
    tracker = MiningTracker()
    tracker.handle(refined(0))
    tracker.handle(refined(5))
    pause = IDLE_THRESHOLD + timedelta(minutes=20)
    tracker.handle(refined(5 + pause.total_seconds() / 60))
    tracker.handle(refined(5 + pause.total_seconds() / 60 + 5))
    assert tracker.session is not None
    assert tracker.session.stats.active_duration == timedelta(minutes=10)


def test_rates_are_zero_without_active_time() -> None:
    tracker = MiningTracker()
    tracker.handle(refined(0))
    assert tracker.session is not None
    assert tracker.session.stats.tons_per_hour == 0.0
    assert tracker.session.stats.refinements_per_minute == 0.0


def test_refinements_per_minute() -> None:
    tracker = MiningTracker()
    for second in range(0, 60, 10):  # 6 refinements within 50 seconds
        tracker.handle(refined(second / 60))
    assert tracker.session is not None
    assert tracker.session.stats.refinements_per_minute == pytest.approx(6 / (50 / 60))


def test_prospecting_is_counted_by_content_level() -> None:
    tracker = MiningTracker()
    tracker.handle(prospected(1, ContentLevel.HIGH))
    tracker.handle(prospected(2, ContentLevel.HIGH))
    tracker.handle(prospected(3, ContentLevel.LOW))
    assert tracker.session is not None
    stats = tracker.session.stats
    assert stats.prospected_total == 3
    assert stats.prospected_by_content == {ContentLevel.HIGH: 2, ContentLevel.LOW: 1}


def test_cores_found_and_cracked() -> None:
    tracker = MiningTracker()
    tracker.handle(prospected(1, motherlode=Commodity.from_symbol("lowtemperaturediamond")))
    tracker.handle(prospected(2))
    tracker.handle(AsteroidCracked(at=at(3)))
    assert tracker.session is not None
    assert tracker.session.stats.cores_found == 1
    assert tracker.session.stats.cores_cracked == 1


def test_limpets_are_counted_by_kind() -> None:
    tracker = MiningTracker()
    tracker.handle(launched(1, LimpetKind.PROSPECTOR))
    tracker.handle(launched(2, LimpetKind.COLLECTOR))
    tracker.handle(launched(3, LimpetKind.COLLECTOR))
    tracker.handle(launched(4, LimpetKind.OTHER))
    assert tracker.session is not None
    assert tracker.session.stats.limpets_launched == {
        LimpetKind.PROSPECTOR: 1,
        LimpetKind.COLLECTOR: 2,
        LimpetKind.OTHER: 1,
    }


def test_cargo_is_tracked_during_a_session_without_counting_as_activity() -> None:
    tracker = MiningTracker()
    tracker.handle(refined(0))
    notifications = tracker.handle(
        CargoChanged(
            at=at(30), total=12, inventory=((PAINITE, 10), (Commodity.from_symbol("drones"), 2))
        )
    )
    assert isinstance(notifications[0], SessionUpdated)
    assert tracker.session is not None
    stats = tracker.session.stats
    assert stats.cargo_tons == 10
    assert stats.limpets_on_board == 2
    assert stats.active_duration == timedelta(0)


def test_ejected_cargo_is_counted_apart() -> None:
    tracker = MiningTracker()
    tracker.handle(refined(0))
    tracker.handle(CargoEjected(at=at(1), commodity=PLATINUM, count=3))
    assert tracker.session is not None
    assert tracker.session.stats.ejected_tons == {PLATINUM: 3}
    assert tracker.session.stats.total_tons == 1


def test_ejected_cargo_outside_a_session_is_ignored() -> None:
    assert MiningTracker().handle(CargoEjected(at=at(1), commodity=PLATINUM, count=3)) == []


# --- sales ------------------------------------------------------------------------------


def sold(
    minutes: float, count: int, commodity: Commodity = PAINITE, price: int = 100
) -> CommoditySold:
    return CommoditySold(
        at=at(minutes), commodity=commodity, count=count, unit_price=price, total=count * price
    )


def only_sale(notifications: list[SessionNotification]) -> SaleRecorded:
    [recorded] = notifications
    assert isinstance(recorded, SaleRecorded)
    return recorded


def docked(minutes: float) -> MiningAreaLeft:
    return MiningAreaLeft(at=at(minutes), reason=LeaveReason.DOCKED)


def test_sale_after_the_session_is_credited_to_it() -> None:
    tracker = MiningTracker()
    for minute in (0, 1, 2):
        tracker.handle(refined(minute))
    tracker.handle(docked(10))
    recorded = only_sale(tracker.handle(sold(12, 3)))
    assert recorded == SaleRecorded(
        at=at(12), commodity=PAINITE, count=3, credits=300, stats=recorded.stats
    )
    assert recorded.stats.sold_tons == {PAINITE: 3}
    assert recorded.stats.credits_earned == 300


def test_only_the_mined_tons_still_unsold_are_credited() -> None:
    tracker = MiningTracker()
    tracker.handle(refined(0))
    tracker.handle(refined(1))
    tracker.handle(docked(5))
    recorded = only_sale(tracker.handle(sold(6, 5)))
    assert (recorded.count, recorded.credits) == (2, 200)
    assert tracker.handle(sold(7, 5)) == []


def test_ejected_tons_cannot_be_sold() -> None:
    tracker = MiningTracker()
    for minute in (0, 1, 2):
        tracker.handle(refined(minute))
    tracker.handle(CargoEjected(at=at(3), commodity=PAINITE, count=1))
    tracker.handle(docked(5))
    recorded = only_sale(tracker.handle(sold(6, 3)))
    assert recorded.count == 2


def test_sale_of_a_commodity_not_mined_is_ignored() -> None:
    tracker = MiningTracker()
    tracker.handle(refined(0))
    tracker.handle(docked(5))
    assert tracker.handle(sold(6, 4, PLATINUM)) == []


def test_sale_without_any_session_is_ignored() -> None:
    assert MiningTracker().handle(sold(0, 4)) == []


def test_sales_go_to_the_latest_session_only() -> None:
    tracker = MiningTracker()
    tracker.handle(refined(0))
    tracker.handle(docked(5))
    tracker.handle(refined(10, PLATINUM))
    tracker.handle(docked(15))
    assert tracker.handle(sold(16, 1)) == []
    recorded = only_sale(tracker.handle(sold(17, 1, PLATINUM)))
    assert recorded.commodity == PLATINUM


def test_sale_during_a_running_session_is_credited_to_it() -> None:
    tracker = MiningTracker()
    tracker.handle(refined(0))
    recorded = only_sale(tracker.handle(sold(1, 1)))
    assert recorded.count == 1
    assert tracker.session is not None
    assert tracker.session.stats.credits_earned == 100


# --- galaxy ------------------------------------------------------------------------------


def test_galaxy_is_live_until_told_otherwise() -> None:
    tracker = MiningTracker()
    assert tracker.is_live is True
    assert tracker.handle(GameLoaded(at=at(0), game_version="3.8.0.407", is_live=False)) == []
    assert tracker.is_live is False


def test_beta_marks_the_game_as_not_live() -> None:
    tracker = MiningTracker()
    tracker.set_beta(True)
    assert tracker.is_live is False
    tracker.set_beta(False)
    assert tracker.is_live is True
