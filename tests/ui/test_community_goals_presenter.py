from datetime import UTC, datetime

from edrockmaster.domain.community_goals.goals import CommunityGoalsChanged
from edrockmaster.domain.community_goals.journal import CommunityGoal
from edrockmaster.ui.community_goals_presenter import CommunityGoalsPresenter
from edrockmaster.ui.panel_model import PanelModel, StatLine

EXPIRY = datetime(2026, 10, 15, 7, 0, tzinfo=UTC)


def goal(**changes: object) -> CommunityGoal:
    values: dict[str, object] = {
        "cgid": 861,
        "title": "Brewer Corporation Hyperspace Satellite Launch Operation",
        "system": "HIP 74116",
        "expiry": EXPIRY,
        "complete": False,
        "contribution": 1_240,
        "percentile_band": 25,
        "tier_reached": "Tier 3",
        "top_tier": "Tier 5",
    }
    values.update(changes)
    return CommunityGoal(**values)  # type: ignore[arg-type]


def test_nothing_joined() -> None:
    assert CommunityGoalsPresenter().render() == PanelModel(
        status="No community goal joined", lines=(), alert=None, can_reset=False
    )


def test_a_goal_shows_its_full_title_its_standing_and_its_expiry() -> None:
    model = CommunityGoalsPresenter().apply([CommunityGoalsChanged((goal(),))])
    assert model.status == "Goals joined: 1"
    assert model.lines == (
        StatLine(
            "Brewer Corporation Hyperspace Satellite Launch Operation, HIP 74116",
            "1,240, top 25 %, tier 3 of 5",
            until=EXPIRY,
        ),
    )
    assert not model.can_reset


def test_a_complete_goal_says_its_reward_is_to_collect() -> None:
    [line] = CommunityGoalsPresenter().apply([CommunityGoalsChanged((goal(complete=True),))]).lines
    assert line.value == "1,240, top 25 %, tier 3 of 5. Complete: reward to collect"
    assert line.until is None


def test_a_goal_with_little_known() -> None:
    little = goal(system=None, expiry=None, percentile_band=None, tier_reached=None, contribution=0)
    [line] = CommunityGoalsPresenter().apply([CommunityGoalsChanged((little,))]).lines
    assert line == StatLine("Brewer Corporation Hyperspace Satellite Launch Operation", "0")


def test_a_system_the_title_names_is_not_repeated() -> None:
    title = "Éliminez les pilotes criminels dans le système Redonesses"
    [line] = (
        CommunityGoalsPresenter()
        .apply([CommunityGoalsChanged((goal(title=title, system="Redonesses"),))])
        .lines
    )
    assert line.label == title


def test_a_tier_not_named_as_usual_is_shown_as_the_game_writes_it() -> None:
    [line] = (
        CommunityGoalsPresenter()
        .apply([CommunityGoalsChanged((goal(tier_reached="Gold", top_tier=None),))])
        .lines
    )
    assert line.value == "1,240, top 25 %, Gold"


def test_a_tier_named_in_french_is_read_too() -> None:
    [line] = (
        CommunityGoalsPresenter()
        .apply([CommunityGoalsChanged((goal(tier_reached="Niveau 1", top_tier="Niveau 5"),))])
        .lines
    )
    assert line.value == "1,240, top 25 %, tier 1 of 5"


def test_render_rebuilds_texts_in_the_current_language() -> None:
    language = {"prefix": ""}
    presenter = CommunityGoalsPresenter(translate=lambda text: language["prefix"] + text)
    presenter.apply([CommunityGoalsChanged((goal(),))])
    language["prefix"] = "fr:"
    assert presenter.render().status == "fr:Goals joined: 1"
