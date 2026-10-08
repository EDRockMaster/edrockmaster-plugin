from datetime import UTC, datetime

from edrockmaster.domain.engineering.catalogue import MaterialCategory
from edrockmaster.domain.engineering.goals import BlueprintGoal, ExperimentalEffectGoal, GoalId
from edrockmaster.domain.engineering.session import (
    CollectionEnded,
    CollectionEndReason,
    CollectionStarted,
    CollectionStats,
    EngineeringStats,
    EngineeringUpdated,
    GoalDone,
    GoalProgress,
    GoalProgressed,
    GoalReady,
    MaterialCapped,
)
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
    )


def test_goals_without_inventory_say_so() -> None:
    model = EngineeringPresenter(names()).apply(
        [updated(None, progress(RANGE, False), known=False)]
    )
    assert model.lines == (StatLine("Goals ready", "inventory unknown"),)


def test_alerts_last_until_a_change_without_one() -> None:
    presenter = EngineeringPresenter(names())
    model = presenter.apply([MaterialCapped("arsenic", None, 250), updated(collection())])
    assert model.alert == "Arsenic at its cap (250)"
    # A statement of the game at load keeps it
    assert presenter.apply([updated(collection(), progressed=False)]).alert == model.alert
    assert presenter.apply([GoalReady(RANGE), updated(collection())]).alert == (
        "Goal ready: Frame shift drive: Increased range, grade 5"
    )
    assert presenter.apply([GoalProgressed(MASS), GoalDone(MASS), updated(collection())]).alert == (
        "Goal done: Frame shift drive: Mass Manager"
    )
    assert presenter.apply([updated(collection())]).alert is None


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
