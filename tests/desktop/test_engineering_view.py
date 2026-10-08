"""The engineering view and the goal form's catalogue (ADR 0017, ADR 0020), real catalogue."""

import json
from datetime import UTC, datetime
from typing import Any

import jsonschema
import pytest

from edrockmaster.application.engineering_service import EngineeringService
from edrockmaster.desktop.engineering_view import (
    BLUEPRINT,
    EFFECT,
    catalogue_view,
    engineering_view,
    goal_from_request,
    with_count,
)
from edrockmaster.desktop.live_view import SCHEMA
from edrockmaster.domain.engineering.goals import BlueprintGoal, ExperimentalEffectGoal, GoalId
from edrockmaster.infrastructure.catalogue_file import load_catalogue
from edrockmaster.ui.engineering_names import EngineeringNames
from tests.fakes import FakeGoalRepository, FixedClock

CATALOGUE = load_catalogue()
SCHEMAS = SCHEMA.parent
LIVE = json.loads(SCHEMA.read_text(encoding="utf-8"))
ENGINEERING = jsonschema.Draft202012Validator(
    {"$defs": LIVE["$defs"], "$ref": "#/$defs/engineering"}
)
GOAL_CATALOGUE = jsonschema.Draft202012Validator(
    json.loads((SCHEMAS / "goal_catalogue.schema.json").read_text(encoding="utf-8"))
)
T0 = "2026-10-08T05:30:00Z"
POWER_DISTRIBUTOR = BlueprintGoal(GoalId("pd"), "PowerDistributor_HighCapacity", "pd", 2, rolls=3)
MASS_MANAGER = ExperimentalEffectGoal(GoalId("mm"), "special_fsd_heavy", "fsd")


def french(text: str) -> str:
    return {"Power distributor": "Distributeur d'énergie"}.get(text, text)


@pytest.fixture
def service() -> EngineeringService:
    service = EngineeringService(
        CATALOGUE,
        FakeGoalRepository([POWER_DISTRIBUTOR, MASS_MANAGER]),
        FixedClock(datetime(2026, 10, 8, tzinfo=UTC)),
    )
    service.load_goals(lambda _notifications: None)
    return service


def names(service: EngineeringService) -> EngineeringNames:
    return EngineeringNames(CATALOGUE, french, service.name_of)


def view(service: EngineeringService) -> dict[str, Any]:
    built = engineering_view(service, names(service))
    ENGINEERING.validate(built)
    return built


def test_before_the_game_states_the_inventory(service: EngineeringService) -> None:
    built = view(service)
    assert not built["inventoryKnown"]
    assert len(built["materials"]) == 137
    assert all(row["count"] == 0 for row in built["materials"])
    assert [goal["missing"] for goal in built["goals"]] == [None, None]
    assert built["catalogueDate"] == "2026-09-05"


def test_materials_by_category_then_grade_with_their_caps(service: EngineeringService) -> None:
    service.handle_journal_entry(
        {
            "timestamp": T0,
            "event": "Materials",
            "Raw": [{"Name": "sulphur", "Name_Localised": "Soufre", "Count": 299}],
            "Encoded": [{"Name": "tg_interdictiondata", "Count": 4}],
        }
    )
    materials = view(service)["materials"]
    assert [row["category"] for row in materials[:1]] == ["raw"]
    categories = [row["category"] for row in materials]
    assert categories.index("manufactured") < categories.index("encoded")
    sulphur = next(row for row in materials if row["symbol"] == "sulphur")
    assert sulphur == {
        "symbol": "sulphur",
        "name": "Soufre",
        "category": "raw",
        "grade": 1,
        "count": 299,
        "cap": 300,
    }
    # Held but unknown to the catalogue: listed last, without category or cap
    assert materials[-1] == {
        "symbol": "tg_interdictiondata",
        "name": "tg_interdictiondata",
        "category": None,
        "grade": None,
        "count": 4,
        "cap": None,
    }


def test_goals_what_they_miss_and_who_offers_them(service: EngineeringService) -> None:
    service.handle_journal_entry(
        {"timestamp": T0, "event": "Materials", "Encoded": [{"Name": "legacyfirmware", "Count": 1}]}
    )
    service.handle_journal_entry(
        {
            "timestamp": T0,
            "event": "EngineerProgress",
            "Engineers": [
                {
                    "Engineer": "Marco Qwent",
                    "EngineerID": 300200,
                    "Progress": "Unlocked",
                    "Rank": 5,
                },
                {"Engineer": "Felicity Farseer", "EngineerID": 300100, "Progress": "Invited"},
            ],
        }
    )
    built = view(service)
    pd, mass = built["goals"]
    assert pd["kind"] == BLUEPRINT
    assert pd["module"] == "Distributeur d'énergie"
    assert (pd["grade"], pd["count"], pd["known"], pd["ready"]) == (2, 3, True, False)
    # Grade 2 takes one Specialised Legacy Firmware and one Chromium a roll: three rolls
    assert {row["symbol"]: (row["count"], row["held"]) for row in pd["missing"]} == {
        "chromium": (3, 0),
        "legacyfirmware": (2, 0),
    }
    assert "Marco Qwent" in pd["engineers"]
    assert mass["kind"] == EFFECT
    assert mass["grade"] is None
    shopping = {row["symbol"]: (row["count"], row["held"]) for row in built["shoppingList"]}
    assert shopping["legacyfirmware"] == (2, 1)
    engineers = {row["name"]: (row["status"], row["rank"]) for row in built["engineers"]}
    assert engineers["Marco Qwent"] == ("unlocked", 5)
    assert engineers["Felicity Farseer"] == ("invited", None)
    assert engineers["Elvira Martuuk"] == (None, None)


def test_the_goal_form_s_catalogue(service: EngineeringService) -> None:
    built = catalogue_view(CATALOGUE, names(service))
    GOAL_CATALOGUE.validate(built)
    assert len(built["modules"]) == 44
    pd = next(module for module in built["modules"] if module["key"] == "pd")
    assert pd["name"] == "Distributeur d'énergie"
    high_capacity = next(
        b for b in pd["blueprints"] if b["name"] == "PowerDistributor_HighCapacity"
    )
    assert high_capacity["grades"] == [1, 2, 3, 4, 5]
    fsd = next(module for module in built["modules"] if module["key"] == "fsd")
    assert any(effect["name"] == "special_fsd_heavy" for effect in fsd["effects"])


def test_a_goal_from_the_form() -> None:
    goal = goal_from_request(
        {"kind": "blueprint", "module": "fsd", "name": "FSD_LongRange", "grade": 5, "count": 4},
        CATALOGUE,
    )
    assert isinstance(goal, BlueprintGoal)
    assert (goal.blueprint, goal.module, goal.grade, goal.rolls) == ("FSD_LongRange", "fsd", 5, 4)
    effect = goal_from_request(
        {"kind": "effect", "module": "fsd", "name": "special_fsd_heavy"}, CATALOGUE
    )
    assert isinstance(effect, ExperimentalEffectGoal)
    assert effect.applications == 1


@pytest.mark.parametrize(
    "request_",
    [
        {"kind": "blueprint", "module": "nowhere", "name": "FSD_LongRange", "grade": 5},
        {"kind": "blueprint", "module": "fsd", "name": "FSD_LongRange", "grade": 6},
        {"kind": "blueprint", "module": "fsd", "name": "Engine_Dirty", "grade": 1},
        {"kind": "effect", "module": "fsd", "name": "special_weapon_damage"},
        {"kind": "wish", "module": "fsd", "name": "FSD_LongRange"},
        {"kind": "blueprint", "module": "fsd", "name": "FSD_LongRange", "grade": 5, "count": 0},
        {"kind": "blueprint", "module": "fsd", "name": 3, "grade": 5},
    ],
)
def test_a_goal_the_catalogue_does_not_offer_is_refused(request_: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match=r"goal|offers|grade|roll"):
        goal_from_request(request_, CATALOGUE)


def test_a_goal_with_a_new_count() -> None:
    assert with_count(POWER_DISTRIBUTOR, 1) == BlueprintGoal(
        GoalId("pd"), "PowerDistributor_HighCapacity", "pd", 2, rolls=1
    )
    assert with_count(MASS_MANAGER, 2).applications == 2  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="application"):
        with_count(MASS_MANAGER, 0)
