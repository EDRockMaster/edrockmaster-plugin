from datetime import UTC, datetime

import pytest

from edrockmaster.domain.engineering.catalogue import MaterialCategory, OnFootKind
from edrockmaster.domain.engineering.collection import CollectionEndReason, CollectionStats
from edrockmaster.domain.engineering.events import (
    CollectionEnded,
    CollectionStarted,
    EngineeringStats,
    EngineeringUpdated,
    GoalDone,
    GoalProgressed,
    GoalReady,
    MaterialCapped,
)
from edrockmaster.domain.engineering.goals import (
    BlueprintGoal,
    ClassUpgradeGoal,
    EngineerUnlockGoal,
    ExperimentalEffectGoal,
    GoalId,
    ModificationGoal,
)
from edrockmaster.domain.engineering.progress import GoalProgress
from edrockmaster.ui.engineering_names import EngineeringNames
from edrockmaster.ui.engineering_presenter import EngineeringPresenter
from edrockmaster.ui.panel_model import StatLine, identity
from tests.domain.engineering.catalogue_data import catalogue

T0 = datetime(2026, 10, 8, 4, 0, tzinfo=UTC)
RANGE = BlueprintGoal(GoalId("range"), "FSD_LongRange", "fsd", grade=5)
MASS = ExperimentalEffectGoal(GoalId("mass"), "special_fsd_heavy", "fsd")


def names(game: dict[str, str] | None = None) -> EngineeringNames:
    known = game or {}
    return EngineeringNames(catalogue(), identity, known.get)


def collection(**kwargs: object) -> CollectionStats:
    values: dict[str, object] = {"started_at": T0, "gained": {}, "used": 0, "capped": ()}
    values.update(kwargs)
    return CollectionStats(**values)  # type: ignore[arg-type]


def updated(
    stats: CollectionStats | None, *goals: GoalProgress, known: bool = True, progressed: bool = True
) -> EngineeringUpdated:
    return EngineeringUpdated(EngineeringStats(stats, goals, known), progressed)


def progress(goal: BlueprintGoal | ExperimentalEffectGoal, ready: bool) -> GoalProgress:
    return GoalProgress(goal, {"arsenic": 1}, {} if ready else {"arsenic": 1}, ())


def test_no_session_at_first() -> None:
    model = EngineeringPresenter(names()).render()
    assert model.status == "No engineering session"
    assert model.lines == ()
    assert not model.can_reset


def test_a_collection_shows_gains_use_caps_and_goals() -> None:
    presenter = EngineeringPresenter(names({"arsenic": "Arsenic (game)"}))
    stats = collection(
        gained={MaterialCategory.RAW: 12, MaterialCategory.ENCODED: 3, None: 4},
        used=7,
        capped=("arsenic", "dataminedwake"),
    )
    model = presenter.apply(
        [CollectionStarted(T0), updated(stats, progress(RANGE, True), progress(MASS, False))]
    )
    assert model.status == "Engineering"
    assert model.can_reset
    assert model.lines == (
        StatLine("Raw gained", "12"),
        StatLine("Encoded gained", "3"),
        StatLine("Other materials gained", "4"),
        StatLine("Materials used", "7"),
        StatLine("At cap", "Arsenic (game), Datamined Wake Exceptions"),
        StatLine("Goals ready", "1 of 2"),
        StatLine("Frame shift drive: Increased range, grade 5", "ready"),
        StatLine("Frame shift drive: Mass Manager", "missing 1 Arsenic (game)"),
    )


def test_a_collection_on_foot_shows_one_tile_with_its_losses() -> None:
    # The kinds are in the On foot view: the card only sums them up
    presenter = EngineeringPresenter(names())
    stats = collection(
        gained={MaterialCategory.RAW: 2},
        gained_on_foot={OnFootKind.DATA: 32, OnFootKind.ITEM: 42, OnFootKind.COMPONENT: 66},
        lost_on_foot=5,
    )
    model = presenter.apply([CollectionStarted(T0), updated(stats)])
    assert model.lines == (
        StatLine("Raw gained", "2"),
        StatLine("On-foot materials", "+140, 5 lost"),
    )


@pytest.mark.parametrize(
    ("gained", "lost", "text"),
    [({OnFootKind.ITEM: 3}, 0, "+3"), ({}, 7, "+0, 7 lost")],
)
def test_the_on_foot_tile_says_only_what_happened(
    gained: dict[OnFootKind, int], lost: int, text: str
) -> None:
    model = EngineeringPresenter(names()).apply(
        [updated(collection(gained_on_foot=gained, lost_on_foot=lost))]
    )
    assert model.lines == (StatLine("On-foot materials", text),)


def test_goals_without_inventory_say_so() -> None:
    model = EngineeringPresenter(names()).apply(
        [updated(None, GoalProgress(RANGE, {"arsenic": 1}, None, ()), known=False)]
    )
    assert model.lines == (
        StatLine("Goals ready", "inventory unknown"),
        StatLine("Frame shift drive: Increased range, grade 5", "inventory unknown"),
    )


def test_alerts_last_until_a_change_without_one() -> None:
    presenter = EngineeringPresenter(names())
    model = presenter.apply([MaterialCapped("arsenic", None, 250), updated(collection())])
    assert model.alert == "Arsenic at its cap (250)"
    # A statement of the game at load keeps it
    assert presenter.apply([updated(collection(), progressed=False)]).alert == model.alert
    assert presenter.apply(
        [GoalReady(RANGE), updated(collection(), progress(RANGE, True))]
    ).alert == ("Goal ready: Frame shift drive: Increased range, grade 5")
    assert presenter.apply([GoalProgressed(MASS), GoalDone(MASS), updated(collection())]).alert == (
        "Goal done: Frame shift drive: Mass Manager"
    )
    assert presenter.apply([updated(collection())]).alert is None


def test_a_ready_goal_s_alert_goes_with_the_goal() -> None:
    presenter = EngineeringPresenter(names())
    ready = presenter.apply([GoalReady(RANGE), updated(collection(), progress(RANGE, True))])
    assert ready.alert == "Goal ready: Frame shift drive: Increased range, grade 5"
    # Another goal changed by the player: the alert stays
    kept = presenter.apply(
        [updated(collection(), progress(RANGE, True), progress(MASS, False), progressed=False)]
    )
    assert kept.alert == ready.alert
    # The player removed it: nothing left to alert about
    removed = presenter.apply([updated(collection(), progress(MASS, False), progressed=False)])
    assert removed.alert is None
    assert removed.lines == (
        StatLine("Goals ready", "0 of 1"),
        StatLine("Frame shift drive: Mass Manager", "missing 1 Arsenic"),
    )


def test_the_end_of_a_collection() -> None:
    presenter = EngineeringPresenter(names())
    presenter.apply([CollectionStarted(T0)])
    model = presenter.apply([CollectionEnded(T0, CollectionEndReason.GAME_CLOSED), updated(None)])
    assert model.status == "Engineering session ended: game closed"
    assert not model.can_reset


def test_names_without_a_catalogue_or_unknown_to_it() -> None:
    bare = EngineeringNames(None, identity)
    assert bare.material("arsenic") == "arsenic"
    assert bare.goal(RANGE) == "fsd: FSD_LongRange, grade 5"
    assert bare.goal(MASS) == "fsd: special_fsd_heavy"
    full = names()
    assert full.material("tg_interdictiondata") == "tg_interdictiondata"
    assert full.blueprint("Gone") == "Gone"
    assert full.effect("special_gone") == "special_gone"
    assert full.module("zz") == "zz"
    assert full.material("arsenic") == "Arsenic"


def test_names_of_suits_weapons_and_class_upgrades() -> None:
    full = names()
    assert full.item("tacticalsuit") == "Dominator suit"
    assert full.item("wpn_unknown") == "wpn_unknown"
    upgrade = ClassUpgradeGoal(GoalId("up"), "tacticalsuit", 1, 3, T0)
    assert full.goal(upgrade) == "Dominator suit: class 1 to 3"
    assert EngineeringNames(None, identity).item("tacticalsuit") == "tacticalsuit"
    backpack = ModificationGoal(GoalId("mod"), "tacticalsuit", "suit_backpackcapacity", T0)
    assert full.goal(backpack) == "Dominator suit: Extra backpack capacity"
    assert full.modification("suit_gone") == "suit_gone"
    assert full.goal(EngineerUnlockGoal(GoalId("kit"), 400004)) == "Unlock Kit Fowler"
    assert EngineeringNames(None, identity).modification("weapon_handling") == "weapon_handling"
    # On foot: the catalogue's name, as it is, when the game gave none (ADR 0027)
    assert full.material("chemicalsample") == "Chemical Sample"


# The goals' summary (ADR 0033): the first three in the player's priority


def goal_lines(*goals: GoalProgress) -> list[tuple[str, str]]:
    model = EngineeringPresenter(names()).apply([updated(None, *goals)])
    return [(line.label, line.value) for line in model.lines[1:]]


def test_a_goal_says_what_it_misses_in_materials_and_units() -> None:
    missing = GoalProgress(RANGE, {}, {"arsenic": 3, "dataminedwake": 2}, ())
    assert goal_lines(missing) == [
        ("Frame shift drive: Increased range, grade 5", "missing 5 units of 2 materials")
    ]


def test_a_goal_ready_alone_says_a_goal_above_took_its_materials() -> None:
    taken = GoalProgress(MASS, {}, {"arsenic": 2}, (), ready_alone=True)
    assert goal_lines(taken) == [("Frame shift drive: Mass Manager", "taken by a goal above")]


def test_a_goal_without_a_recipe_or_counted_otherwise_says_so() -> None:
    unknown = GoalProgress(RANGE, {}, None, (), known=False)
    unlock = GoalProgress(EngineerUnlockGoal(GoalId("unlock"), 300100), {}, {}, (), counted=False)
    assert goal_lines(unknown, unlock) == [
        ("Frame shift drive: Increased range, grade 5", "recipe unknown"),
        ("Unlock Felicity Farseer", "conditions to meet in game"),
    ]


def test_only_the_first_three_goals_are_listed_then_how_many_more() -> None:
    goals = [
        GoalProgress(BlueprintGoal(GoalId(f"g{n}"), "FSD_LongRange", "fsd", grade=5), {}, {}, ())
        for n in range(5)
    ]
    lines = goal_lines(*goals)
    assert len(lines) == 4
    assert lines[-1] == ("Other goals", "2")
