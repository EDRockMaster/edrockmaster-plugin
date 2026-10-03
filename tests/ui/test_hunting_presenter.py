from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import pytest

from edrockmaster.domain.bounty.hunting import (
    CommunityGoalsChanged,
    HuntEnded,
    HuntEndReason,
    HuntStarted,
    HuntStats,
    HuntUpdated,
    Vouchers,
    VouchersUpdated,
)
from edrockmaster.domain.bounty.journal import CommunityGoal
from edrockmaster.ui.hunting_presenter import HuntingPresenter
from edrockmaster.ui.panel_model import PanelModel

T0 = datetime(2026, 10, 3, 21, 0, tzinfo=UTC)


def stats(minutes: float = 30, **changes: int) -> HuntStats:
    values = {"kills": 6, "shared_kills": 0, "bounty_credits": 900_000, "bond_credits": 0}
    values.update(changes)
    return HuntStats(started_at=T0, active_duration=timedelta(minutes=minutes), **values)


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
def presenter() -> HuntingPresenter:
    return HuntingPresenter()


def test_nothing_to_show_before_any_hunt(presenter: HuntingPresenter) -> None:
    assert presenter.render() == PanelModel(
        status="No hunting session", lines=(), alert=None, can_reset=False
    )


def test_running_hunt(presenter: HuntingPresenter) -> None:
    model = presenter.apply([HuntStarted(T0), HuntUpdated(stats())])
    assert model.status == "Bounty hunting"
    assert model.can_reset
    assert model.alert is None
    assert labels(model) == ["Active time", "Kills", "Bounties", "Rate"]
    assert value(model, "Active time") == "30 min"
    assert value(model, "Kills") == "6"
    assert value(model, "Bounties") == "900,000 CR"
    assert value(model, "Rate") == "1,800,000 CR/h"


def test_shared_kills_and_combat_bonds_appear_when_present(presenter: HuntingPresenter) -> None:
    model = presenter.apply([HuntUpdated(stats(shared_kills=2, bond_credits=120_000))])
    assert value(model, "Kills") == "6 (2 shared)"
    assert value(model, "Combat bonds") == "120,000 CR"


@pytest.mark.parametrize(
    ("reason", "status"),
    [
        (HuntEndReason.GAME_CLOSED, "Hunt ended: game closed"),
        (HuntEndReason.DIED, "Hunt ended: ship destroyed"),
        (HuntEndReason.MANUAL, "Hunt ended: reset"),
    ],
)
def test_ended_hunt_keeps_its_statistics(
    presenter: HuntingPresenter, reason: HuntEndReason, status: str
) -> None:
    model = presenter.apply([HuntStarted(T0), HuntEnded(T0, reason, stats())])
    assert model.status == status
    assert not model.can_reset
    assert value(model, "Kills") == "6"


def test_unredeemed_vouchers_are_shown_while_there_are_some(presenter: HuntingPresenter) -> None:
    model = presenter.apply([VouchersUpdated(vouchers(bounties=900_000, bonds=100_000))])
    assert value(model, "Unredeemed") == "1,000,000 CR"
    assert "Unredeemed" not in labels(presenter.apply([VouchersUpdated(vouchers())]))


def test_community_goals_are_listed(presenter: HuntingPresenter) -> None:
    model = presenter.apply([CommunityGoalsChanged((goal(),))])
    assert value(model, "Defend the Sirius Gate") == "25,000,000, top 25 %, Tier 4"


def test_community_goal_with_little_known(presenter: HuntingPresenter) -> None:
    model = presenter.apply(
        [CommunityGoalsChanged((goal(percentile_band=None, tier_reached=None, contribution=0),))]
    )
    assert value(model, "Defend the Sirius Gate") == "0"


def test_completed_community_goals_are_marked(presenter: HuntingPresenter) -> None:
    model = presenter.apply([CommunityGoalsChanged((goal(complete=True),))])
    assert value(model, "Defend the Sirius Gate").endswith("(complete)")


def test_render_rebuilds_texts_in_the_current_language() -> None:
    language = {"prefix": ""}
    presenter = HuntingPresenter(translate=lambda text: language["prefix"] + text)
    presenter.apply([HuntStarted(T0), HuntUpdated(stats())])
    language["prefix"] = "fr:"
    assert presenter.render().status == "fr:Bounty hunting"


def test_long_community_goal_titles_are_shortened(presenter: HuntingPresenter) -> None:
    title = "Defend the Sirius Gate against the Thargoid incursion"
    [line] = presenter.apply([CommunityGoalsChanged((goal(title=title),))]).lines
    assert len(line.label) <= 32
    assert line.label.endswith("…")
    assert title.startswith(line.label[:-1])


def test_bounties_are_left_out_when_only_combat_bonds_were_earned(
    presenter: HuntingPresenter,
) -> None:
    model = presenter.apply([HuntUpdated(stats(bounty_credits=0, bond_credits=224_467))])
    assert "Bounties" not in labels(model)
    assert value(model, "Combat bonds") == "224,467 CR"


def test_only_combat_bonds_is_a_conflict_zone(presenter: HuntingPresenter) -> None:
    bonds_only = stats(bounty_credits=0, bond_credits=224_467)
    assert presenter.apply([HuntStarted(T0), HuntUpdated(bonds_only)]).status == "Conflict zone"
    ended = presenter.apply([HuntEnded(T0, HuntEndReason.MANUAL, bonds_only)])
    assert ended.status == "Conflict zone ended: reset"


def test_any_bounty_makes_it_bounty_hunting(presenter: HuntingPresenter) -> None:
    mixed = stats(bounty_credits=100_000, bond_credits=224_467)
    assert presenter.apply([HuntStarted(T0), HuntUpdated(mixed)]).status == "Bounty hunting"
