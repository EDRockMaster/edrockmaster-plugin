from datetime import UTC, datetime, timedelta
from types import MappingProxyType

from edrockmaster.application.activity import Activity
from edrockmaster.domain.combat.session import (
    CombatStarted,
    CombatStats,
    CombatUpdated,
    CommunityGoalsChanged,
    Crimes,
    SegmentStats,
    Tally,
    Vouchers,
    VouchersUpdated,
)
from edrockmaster.domain.combat.sites import SiteType
from edrockmaster.domain.mining.session import SessionStarted
from edrockmaster.ui.presenter import ActivityPresenter

T0 = datetime(2026, 10, 3, 21, 0, tzinfo=UTC)
SEGMENT = SegmentStats(
    SiteType.RES_HAZARDOUS, T0, timedelta(minutes=10), Tally(kills=1, bounty_credits=100_000)
)
STATS = CombatStats(T0, (SEGMENT,), SEGMENT, Tally(), Crimes())
VOUCHERS = Vouchers(bounties=MappingProxyType({"Federation": 100_000}), combat_bonds={})


def shown(presenter: ActivityPresenter) -> Activity:
    return presenter.current


def test_mining_is_shown_by_default() -> None:
    presenter = ActivityPresenter()
    assert presenter.current is Activity.MINING
    assert presenter.render().status == "No mining session"


def test_the_last_activity_to_progress_is_shown() -> None:
    presenter = ActivityPresenter()
    model = presenter.apply([CombatStarted(T0), CombatUpdated(STATS), VouchersUpdated(VOUCHERS)])
    assert shown(presenter) is Activity.COMBAT
    assert model.status == "RES, hazardous"
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
    presenter.apply([CombatStarted(T0)])
    presenter.apply([SessionStarted(T0, None, None)])
    presenter.apply([VouchersUpdated(VOUCHERS)])
    model = presenter.apply([CombatUpdated(STATS)])
    assert ("Unredeemed", "100,000 CR") in [(line.label, line.value) for line in model.lines]


def test_translation_reaches_both_presenters() -> None:
    presenter = ActivityPresenter(translate=lambda text: f"<{text}>")
    assert presenter.render().status == "<No mining session>"
    assert presenter.apply([CombatStarted(T0)]).status == "<Combat>"
