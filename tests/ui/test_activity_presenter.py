from datetime import UTC, datetime, timedelta
from types import MappingProxyType

from edrockmaster.application.activity import Activity
from edrockmaster.domain.bounty.hunting import (
    CommunityGoalsChanged,
    HuntStarted,
    HuntStats,
    HuntUpdated,
    Vouchers,
    VouchersUpdated,
)
from edrockmaster.domain.mining.session import SessionStarted
from edrockmaster.ui.presenter import ActivityPresenter

T0 = datetime(2026, 10, 3, 21, 0, tzinfo=UTC)
STATS = HuntStats(
    started_at=T0,
    active_duration=timedelta(minutes=10),
    kills=1,
    shared_kills=0,
    bounty_credits=100_000,
    bond_credits=0,
)
VOUCHERS = Vouchers(bounties=MappingProxyType({"Federation": 100_000}), combat_bonds={})


def shown(presenter: ActivityPresenter) -> Activity:
    return presenter.current


def test_mining_is_shown_by_default() -> None:
    presenter = ActivityPresenter()
    assert presenter.current is Activity.MINING
    assert presenter.render().status == "No mining session"


def test_the_last_activity_to_progress_is_shown() -> None:
    presenter = ActivityPresenter()
    model = presenter.apply([HuntStarted(T0), HuntUpdated(STATS), VouchersUpdated(VOUCHERS)])
    assert shown(presenter) is Activity.BOUNTY_HUNTING
    assert model.status == "Bounty hunting"
    model = presenter.apply([SessionStarted(T0, None, "Col 285 2 A Ring")])
    assert shown(presenter) is Activity.MINING
    assert model.status == "Mining: Col 285 2 A Ring"


def test_vouchers_and_goals_do_not_switch_the_activity() -> None:
    presenter = ActivityPresenter()
    presenter.apply([SessionStarted(T0, None, None)])
    presenter.apply([VouchersUpdated(VOUCHERS), CommunityGoalsChanged(())])
    assert presenter.current is Activity.MINING


def test_hidden_activity_keeps_up_to_date() -> None:
    presenter = ActivityPresenter()
    presenter.apply([HuntStarted(T0)])
    presenter.apply([SessionStarted(T0, None, None)])
    presenter.apply([VouchersUpdated(VOUCHERS)])
    model = presenter.apply([HuntUpdated(STATS)])
    assert ("Unredeemed", "100,000 CR") in [(line.label, line.value) for line in model.lines]


def test_translation_reaches_both_presenters() -> None:
    presenter = ActivityPresenter(translate=lambda text: f"<{text}>")
    assert presenter.render().status == "<No mining session>"
    assert presenter.apply([HuntStarted(T0)]).status == "<Bounty hunting>"
