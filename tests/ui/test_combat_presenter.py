from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import pytest

from edrockmaster.domain.combat.journal import CommunityGoal
from edrockmaster.domain.combat.session import (
    CombatEnded,
    CombatEndReason,
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
from edrockmaster.ui.combat_presenter import SITE_NAMES, CombatPresenter
from edrockmaster.ui.panel_model import PanelModel

T0 = datetime(2026, 10, 3, 21, 0, tzinfo=UTC)
CZ = SiteType.CONFLICT_ZONE_HIGH
NOTHING = Tally()
NO_CRIME = Crimes()


def segment(
    minutes: float = 30, site: SiteType = SiteType.RES_HAZARDOUS, **tally: int
) -> SegmentStats:
    values = {"kills": 6, "bounty_credits": 900_000}
    values.update(tally)
    return SegmentStats(site, T0, timedelta(minutes=minutes), Tally(**values))


def stats(
    *segments: SegmentStats,
    current: bool = True,
    miscellaneous: Tally = NOTHING,
    crimes: Crimes = NO_CRIME,
) -> CombatStats:
    segments = segments or (segment(),)
    return CombatStats(
        started_at=T0,
        segments=segments,
        current=segments[-1] if current else None,
        miscellaneous=miscellaneous,
        crimes=crimes,
    )


def vouchers(bounties: int = 0, bonds: int = 0) -> Vouchers:
    return Vouchers(
        bounties=MappingProxyType({"Federation": bounties} if bounties else {}),
        combat_bonds=MappingProxyType({"Federation": bonds} if bonds else {}),
    )


def goal(**changes: object) -> CommunityGoal:
    values: dict[str, object] = {
        "cgid": 812,
        "title": "Defend the Sirius Gate",
        "system": "Sirius",
        "expiry": None,
        "complete": False,
        "contribution": 25_000_000,
        "percentile_band": 25,
        "tier_reached": "Tier 4",
        "top_tier": "Tier 8",
    }
    values.update(changes)
    return CommunityGoal(**values)  # type: ignore[arg-type]


def value(model: PanelModel, label: str) -> str:
    [line] = [line for line in model.lines if line.label == label]
    return line.value


def labels(model: PanelModel) -> list[str]:
    return [line.label for line in model.lines]


@pytest.fixture
def presenter() -> CombatPresenter:
    return CombatPresenter()


def test_nothing_to_show_before_any_combat(presenter: CombatPresenter) -> None:
    assert presenter.render() == PanelModel(
        status="No combat session", lines=(), alert=None, can_reset=False
    )


def test_on_a_combat_site(presenter: CombatPresenter) -> None:
    model = presenter.apply([CombatStarted(T0), CombatUpdated(stats())])
    assert model.status == "RES, hazardous"
    assert model.can_reset
    assert model.alert is None
    assert labels(model) == ["Active time", "Kills", "Bounties", "This site", "RES, hazardous"]
    assert value(model, "Active time") == "30 min"
    assert value(model, "Kills") == "6"
    assert value(model, "Bounties") == "900,000 CR"
    assert value(model, "This site") == "30 min, kills: 6"
    assert value(model, "RES, hazardous") == "12.0 kills/h, 1,800,000 CR/h"


def test_a_ground_conflict_zone_shows_its_settlement(presenter: CombatPresenter) -> None:
    ground = SegmentStats(
        SiteType.GROUND_CONFLICT_ZONE, T0, timedelta(minutes=15), Tally(kills=9), "Pak's Habitat"
    )
    model = presenter.apply([CombatStarted(T0), CombatUpdated(stats(ground))])
    assert model.status == "Ground conflict zone: Pak's Habitat"
    assert value(model, "Ground conflict zone") == "36.0 kills/h, 0 CR/h"


@pytest.mark.parametrize("site", list(SiteType))
def test_every_site_type_has_a_name(presenter: CombatPresenter, site: SiteType) -> None:
    model = presenter.apply([CombatStarted(T0), CombatUpdated(stats(segment(site=site)))])
    assert model.status == SITE_NAMES[site]


def test_between_sites(presenter: CombatPresenter) -> None:
    model = presenter.apply([CombatStarted(T0), CombatUpdated(stats(current=False))])
    assert model.status == "Combat"
    assert "This site" not in labels(model)


def test_one_average_per_site_type(presenter: CombatPresenter) -> None:
    conflict = segment(60, CZ, bounty_credits=0, bond_credits=600_000, kills=20)
    model = presenter.apply([CombatUpdated(stats(segment(), conflict, current=False))])
    assert value(model, "RES, hazardous") == "12.0 kills/h, 1,800,000 CR/h"
    assert value(model, "Conflict zone, high") == "20.0 kills/h, 600,000 CR/h"
    assert value(model, "Active time") == "1 h 30 min"


def test_miscellaneous_kills(presenter: CombatPresenter) -> None:
    misc = Tally(kills=1, bounty_credits=370_130)
    model = presenter.apply([CombatUpdated(stats(miscellaneous=misc))])
    assert value(model, "Miscellaneous") == "kills: 1, 370,130 CR"
    assert value(model, "Kills") == "7"


def test_only_miscellaneous_kills_show_no_active_time(presenter: CombatPresenter) -> None:
    misc = Tally(kills=1, bounty_credits=370_130)
    model = presenter.apply([CombatUpdated(CombatStats(T0, (), None, misc, Crimes()))])
    assert labels(model) == ["Kills", "Bounties", "Miscellaneous"]


def test_crimes(presenter: CombatPresenter) -> None:
    crimes = Crimes(count=2, fines=100, bounties=400, by_kind=MappingProxyType({"assault": 2}))
    model = presenter.apply([CombatUpdated(stats(crimes=crimes))])
    assert value(model, "Fines") == "100 CR"
    assert value(model, "Bounty on you") == "400 CR"
    assert "Fines" not in labels(presenter.apply([CombatUpdated(stats())]))


def test_shared_kills_and_combat_bonds_appear_when_present(presenter: CombatPresenter) -> None:
    model = presenter.apply([CombatUpdated(stats(segment(shared_kills=2, bond_credits=120_000)))])
    assert value(model, "Kills") == "6 (2 shared)"
    assert value(model, "Combat bonds") == "120,000 CR"


def test_bounties_are_left_out_when_only_combat_bonds_were_earned(
    presenter: CombatPresenter,
) -> None:
    model = presenter.apply(
        [CombatUpdated(stats(segment(site=CZ, bounty_credits=0, bond_credits=224_467)))]
    )
    assert "Bounties" not in labels(model)
    assert value(model, "Combat bonds") == "224,467 CR"


@pytest.mark.parametrize(
    ("reason", "status"),
    [
        (CombatEndReason.GAME_CLOSED, "Combat session ended: game closed"),
        (CombatEndReason.DIED, "Combat session ended: ship destroyed"),
        (CombatEndReason.MANUAL, "Combat session ended: reset"),
    ],
)
def test_ended_combat_keeps_its_statistics(
    presenter: CombatPresenter, reason: CombatEndReason, status: str
) -> None:
    model = presenter.apply([CombatStarted(T0), CombatEnded(T0, reason, stats(current=False))])
    assert model.status == status
    assert not model.can_reset
    assert value(model, "Kills") == "6"


def test_unredeemed_vouchers_are_shown_while_there_are_some(presenter: CombatPresenter) -> None:
    model = presenter.apply([VouchersUpdated(vouchers(bounties=900_000, bonds=100_000))])
    assert value(model, "Unredeemed") == "1,000,000 CR"
    assert "Unredeemed" not in labels(presenter.apply([VouchersUpdated(vouchers())]))


def test_community_goals_are_listed(presenter: CombatPresenter) -> None:
    model = presenter.apply([CommunityGoalsChanged((goal(),))])
    assert value(model, "Defend the Sirius Gate") == "25,000,000, top 25 %, Tier 4"


def test_community_goal_with_little_known(presenter: CombatPresenter) -> None:
    model = presenter.apply(
        [CommunityGoalsChanged((goal(percentile_band=None, tier_reached=None, contribution=0),))]
    )
    assert value(model, "Defend the Sirius Gate") == "0"


def test_completed_community_goals_are_marked(presenter: CombatPresenter) -> None:
    model = presenter.apply([CommunityGoalsChanged((goal(complete=True),))])
    assert value(model, "Defend the Sirius Gate").endswith("(complete)")


def test_render_rebuilds_texts_in_the_current_language() -> None:
    language = {"prefix": ""}
    presenter = CombatPresenter(translate=lambda text: language["prefix"] + text)
    presenter.apply([CombatStarted(T0), CombatUpdated(stats())])
    language["prefix"] = "fr:"
    assert presenter.render().status == "fr:RES, hazardous"


def test_long_community_goal_titles_are_shortened(presenter: CombatPresenter) -> None:
    title = "Defend the Sirius Gate against the Thargoid incursion"
    [line] = presenter.apply([CommunityGoalsChanged((goal(title=title),))]).lines
    assert len(line.label) <= 32
    assert line.label.endswith("…")
    assert title.startswith(line.label[:-1])
