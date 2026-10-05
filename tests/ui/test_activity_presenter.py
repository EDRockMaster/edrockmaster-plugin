from datetime import UTC, datetime, timedelta
from types import MappingProxyType

from edrockmaster.application.activity import Activity
from edrockmaster.application.settings import DisplayMode, DisplaySettings
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

COMBAT_ONLY = DisplaySettings(activities=(Activity.COMBAT,))
STACKED = DisplaySettings(mode=DisplayMode.STACKED)

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


def statuses(presenter: ActivityPresenter) -> list[tuple[Activity, str]]:
    return [(block.activity, block.model.status) for block in presenter.blocks()]


def test_last_active_mode_shows_one_block() -> None:
    presenter = ActivityPresenter()
    presenter.apply([CombatStarted(T0)])
    assert statuses(presenter) == [(Activity.COMBAT, "Combat")]


def test_stacked_mode_shows_a_block_per_activity_in_display_order() -> None:
    presenter = ActivityPresenter(display=STACKED)
    presenter.apply([CombatStarted(T0), SessionStarted(T0, None, None)])
    assert statuses(presenter) == [
        (Activity.MINING, "Mining"),
        (Activity.COMBAT, "Combat"),
    ]


def test_stacked_mode_only_shows_the_activities_chosen() -> None:
    presenter = ActivityPresenter(display=DisplaySettings((Activity.COMBAT,), DisplayMode.STACKED))
    assert statuses(presenter) == [(Activity.COMBAT, "No combat session")]


def test_a_hidden_activity_never_takes_the_panel() -> None:
    presenter = ActivityPresenter(display=COMBAT_ONLY)
    assert presenter.current is Activity.COMBAT
    presenter.apply([CombatStarted(T0), SessionStarted(T0, None, None)])
    assert presenter.current is Activity.COMBAT
    assert statuses(presenter) == [(Activity.COMBAT, "Combat")]


def test_hiding_the_activity_shown_moves_to_one_still_shown() -> None:
    presenter = ActivityPresenter()
    presenter.apply([SessionStarted(T0, None, None)])
    presenter.configure(COMBAT_ONLY)
    assert presenter.current is Activity.COMBAT
    presenter.configure(DisplaySettings())
    assert presenter.current is Activity.COMBAT  # what is shown stays put


def test_a_hidden_activity_keeps_up_to_date_for_when_it_is_shown_again() -> None:
    presenter = ActivityPresenter(display=COMBAT_ONLY)
    presenter.apply([SessionStarted(T0, None, "Col 285 2 A Ring")])
    presenter.configure(STACKED)
    assert statuses(presenter)[0] == (Activity.MINING, "Mining: Col 285 2 A Ring")
