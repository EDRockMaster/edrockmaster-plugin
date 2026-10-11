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
from edrockmaster.domain.engineering.goals import (
    BlueprintGoal,
    ClassUpgradeGoal,
    ExperimentalEffectGoal,
    GoalId,
)
from edrockmaster.domain.engineering.on_foot_journal import Suit
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
NOW = datetime(2026, 10, 11, 1, 30, tzinfo=UTC)
POWER_DISTRIBUTOR = BlueprintGoal(GoalId("pd"), "PowerDistributor_HighCapacity", "pd", 2, rolls=3)
MASS_MANAGER = ExperimentalEffectGoal(GoalId("mm"), "special_fsd_heavy", "fsd")


def french(text: str) -> str:
    return {
        "Power distributor": "Distributeur d'énergie",
        "Professor Palin": "Professeur Palin",
    }.get(text, text)


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
    # Engineers are named in the player's language, and sorted by that name
    assert "Professeur Palin" in engineers
    assert "Professor Palin" not in engineers
    ordered = [row["name"] for row in built["engineers"]]
    assert ordered == sorted(ordered, key=str.casefold)


def test_an_engineer_s_name(service: EngineeringService) -> None:
    palin = next(id_ for id_, name in CATALOGUE.engineers.items() if name == "Professor Palin")
    assert names(service).engineer(palin) == "Professeur Palin"
    assert names(service).engineer(1) == "1"  # not in the catalogue
    assert EngineeringNames(None, french).engineer(palin) == str(palin)


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


def test_the_catalogue_s_recipes_for_the_blueprints_tab(service: EngineeringService) -> None:
    built = catalogue_view(CATALOGUE, names(service))
    pd = next(module for module in built["modules"] if module["key"] == "pd")
    high_capacity = next(
        b for b in pd["blueprints"] if b["name"] == "PowerDistributor_HighCapacity"
    )
    recipes = {recipe["grade"]: recipe for recipe in high_capacity["recipes"]}
    assert sorted(recipes) == high_capacity["grades"]
    # Grade 2: one Specialised Legacy Firmware and one Chromium a roll
    assert {row["symbol"]: row["count"] for row in recipes[2]["ingredients"]} == {
        "chromium": 1,
        "legacyfirmware": 1,
    }
    marco_qwent = next(i for i, name in CATALOGUE.engineers.items() if name == "Marco Qwent")
    assert marco_qwent in recipes[2]["engineers"]
    assert marco_qwent not in recipes[5]["engineers"]  # up to grade 4
    fsd = next(module for module in built["modules"] if module["key"] == "fsd")
    mass_manager = next(e for e in fsd["effects"] if e["name"] == "special_fsd_heavy")
    assert mass_manager["ingredients"]
    assert all(row["name"] and row["count"] >= 1 for row in mass_manager["ingredients"])


def test_a_goal_from_the_form() -> None:
    goal = goal_from_request(
        {"kind": "blueprint", "module": "fsd", "name": "FSD_LongRange", "grade": 5, "count": 4},
        CATALOGUE,
        {},
        NOW,
    )
    assert isinstance(goal, BlueprintGoal)
    assert (goal.blueprint, goal.module, goal.grade, goal.rolls) == ("FSD_LongRange", "fsd", 5, 4)
    effect = goal_from_request(
        {"kind": "effect", "module": "fsd", "name": "special_fsd_heavy"}, CATALOGUE, {}, NOW
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
        goal_from_request(request_, CATALOGUE, {}, NOW)


def test_a_goal_with_a_new_count() -> None:
    assert with_count(POWER_DISTRIBUTOR, 1) == BlueprintGoal(
        GoalId("pd"), "PowerDistributor_HighCapacity", "pd", 2, rolls=1
    )
    assert with_count(MASS_MANAGER, 2).applications == 2  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="application"):
        with_count(MASS_MANAGER, 0)


DOMINATOR = Suit(1878707285049801, "tacticalsuit", 2, ())
ECLIPSE = "wpn_m_submachinegun_laser_fauto"


def test_a_class_upgrade_from_the_form() -> None:
    # The player's own item: the goal follows it, from its class
    mine = goal_from_request(
        {"kind": "classUpgrade", "item": "tacticalsuit", "toClass": 4, "equipmentId": DOMINATOR.id},
        CATALOGUE,
        {DOMINATOR.id: DOMINATOR},
        NOW,
    )
    assert isinstance(mine, ClassUpgradeGoal)
    assert (mine.item, mine.from_class, mine.to_class, mine.equipment_id) == (
        "tacticalsuit",
        2,
        4,
        DOMINATOR.id,
    )
    assert mine.set_at == NOW
    # A type: from the class the player says, 1 by default
    weapon = goal_from_request(
        {"kind": "classUpgrade", "item": ECLIPSE, "toClass": 3}, CATALOGUE, {}, NOW
    )
    assert isinstance(weapon, ClassUpgradeGoal)
    assert (weapon.from_class, weapon.to_class, weapon.equipment_id) == (1, 3, None)


@pytest.mark.parametrize(
    "request_",
    [
        {"kind": "classUpgrade", "item": "helmet", "toClass": 3},
        {
            "kind": "classUpgrade",
            "item": "tacticalsuit",
            "toClass": 2,
            "equipmentId": 1878707285049801,
        },
        {"kind": "classUpgrade", "item": "tacticalsuit", "toClass": 6},
        {
            "kind": "classUpgrade",
            "item": "utilitysuit",
            "toClass": 4,
            "equipmentId": 1878707285049801,
        },
        {"kind": "classUpgrade", "item": "tacticalsuit", "toClass": 4, "equipmentId": 9},
        {"kind": "classUpgrade", "item": "tacticalsuit", "toClass": "4"},
    ],
)
def test_a_class_upgrade_the_form_cannot_ask_for(request_: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match=r"goal|class|item"):
        goal_from_request(request_, CATALOGUE, {DOMINATOR.id: DOMINATOR}, NOW)


def test_a_class_upgrade_aiming_at_another_class() -> None:
    goal = ClassUpgradeGoal(GoalId("up"), "tacticalsuit", 1, 3, NOW)
    assert with_count(goal, 5) == ClassUpgradeGoal(GoalId("up"), "tacticalsuit", 1, 5, NOW)
    with pytest.raises(ValueError, match="class"):
        with_count(goal, 1)


def test_class_upgrade_goals_on_foot(service: EngineeringService) -> None:
    service.add_goal(ClassUpgradeGoal(GoalId("up"), "tacticalsuit", 2, 5, NOW, DOMINATOR.id))
    part = on_foot(
        service,
        {
            "event": "ShipLocker",
            "Items": [
                {"Name": "suitschematic", "Name_Localised": "Plan de combinaison", "Count": 3}
            ],
            "Components": [{"Name": "graphene", "Name_Localised": "Graphène", "Count": 20}],
            "Consumables": [],
            "Data": [],
        },
    )
    [goal] = part["goals"]
    assert goal["title"] == "Dominator suit"
    assert (goal["item"], goal["equipmentId"], goal["fromClass"], goal["toClass"]) == (
        "tacticalsuit",
        DOMINATOR.id,
        2,
        5,
    )
    # To class 3 and 4 known (one deduced), to class 5 not seen yet (ADR 0030)
    assert goal["known"] is False
    assert goal["unknownClasses"] == [5]
    assert goal["unverified"] is True
    assert goal["credits"] == 6_750_000
    assert goal["ready"] is False
    missing = {row["symbol"]: row["count"] for row in goal["missing"]}
    assert missing == {
        "healthmonitor": 6,
        "manufacturinginstructions": 6,
        "suitschematic": 3,
        "titaniumplating": 14,
    }
    assert {row["symbol"]: row["held"] for row in part["shoppingList"]}["suitschematic"] == 3
    assert part["credits"] == 6_750_000
    # The ship's goals and list hold no on-foot goal
    assert all(row["kind"] != "classUpgrade" for row in view(service)["goals"])


def test_the_goal_form_s_suits_and_weapons(service: EngineeringService) -> None:
    items = catalogue_view(CATALOGUE, names(service))["onFootItems"]
    assert [row["kind"] for row in items][:4] == ["suit"] * 4
    dominator = next(row for row in items if row["symbol"] == "tacticalsuit")
    assert dominator["name"] == "Dominator suit"
    assert [(row["toClass"], row["confidence"]) for row in dominator["upgrades"]] == [
        (2, "game"),
        (3, "deduced"),
        (4, "game"),
    ]
    assert dominator["upgrades"][0]["credits"] == 600_000
    assert {row["symbol"] for row in dominator["upgrades"][0]["ingredients"]} == {
        "graphene",
        "healthmonitor",
        "manufacturinginstructions",
        "suitschematic",
        "titaniumplating",
    }
    eclipse = next(row for row in items if row["symbol"] == ECLIPSE)
    assert (eclipse["kind"], eclipse["name"]) == ("weapon", "TK Eclipse")


def on_foot(service: EngineeringService, *entries: dict[str, Any]) -> dict[str, Any]:
    for entry in entries:
        service.handle_journal_entry({"timestamp": T0, **entry})
    part: dict[str, Any] = view(service)["onFoot"]
    return part


def test_on_foot_before_the_game_states_the_locker(service: EngineeringService) -> None:
    part = on_foot(service)
    assert part["known"] is False
    assert part["materials"] == []
    assert part["carrierMoves"] == []
    # The 13 on-foot engineers, even before the game states them
    assert len(part["engineers"]) == 13
    assert {row["status"] for row in part["engineers"]} == {None}


def test_on_foot_materials_held_by_kind_and_place(service: EngineeringService) -> None:
    part = on_foot(
        service,
        {
            "event": "ShipLocker",
            "Items": [
                {"Name": "gmeds", "Name_Localised": "Traitement gravitationnel", "Count": 3},
                {"Name": "insight", "MissionID": 1, "Count": 1},
            ],
            "Components": [{"Name": "graphene", "Name_Localised": "Graphène", "Count": 2}],
            "Consumables": [{"Name": "healthpack", "Name_Localised": "Médikit", "Count": 95}],
            "Data": [],
        },
        {
            "event": "BackpackChange",
            "Added": [{"Name": "gmeds", "Count": 1, "Type": "Item"}],
        },
    )
    assert part["known"] is True
    assert part["materials"] == [
        {
            "symbol": "insight",
            "name": "Insight",
            "kind": "item",
            "locker": 0,
            "backpack": 0,
            "mission": 1,
        },
        {
            "symbol": "gmeds",
            "name": "Traitement gravitationnel",
            "kind": "item",
            "locker": 3,
            "backpack": 1,
            "mission": 0,
        },
        {
            "symbol": "graphene",
            "name": "Graphène",
            "kind": "component",
            "locker": 2,
            "backpack": 0,
            "mission": 0,
        },
        {
            "symbol": "healthpack",
            "name": "Médikit",
            "kind": "consumable",
            "locker": 95,
            "backpack": 0,
            "mission": 0,
        },
    ]


def test_on_foot_engineers_and_equipment(service: EngineeringService) -> None:
    part = on_foot(
        service,
        {
            "event": "EngineerProgress",
            "Engineers": [
                {"Engineer": "Domino Green", "EngineerID": 400002, "Progress": "Invited"},
                {
                    "Engineer": "Marco Qwent",
                    "EngineerID": 300200,
                    "Progress": "Unlocked",
                    "Rank": 4,
                },
            ],
        },
        {
            "event": "SuitLoadout",
            "SuitID": 1,
            "SuitName": "utilitysuit_class2",
            "SuitMods": [],
            "Modules": [
                {
                    "SlotName": "PrimaryWeapon1",
                    "SuitModuleID": 2,
                    "ModuleName": "wpn_m_submachinegun_kinetic_fauto",
                    "ModuleName_Localised": "Karma C-44",
                    "Class": 1,
                    "WeaponMods": [],
                }
            ],
        },
    )
    domino = next(row for row in part["engineers"] if row["id"] == 400002)
    assert domino == {"id": 400002, "name": "Domino Green", "status": "invited"}
    # Ship engineers stay in the ship part
    assert all(row["id"] > 400000 for row in part["engineers"])
    assert part["equipment"] == [
        {"id": 1, "kind": "suit", "symbol": "utilitysuit", "name": "Maverick suit", "class": 2},
        {
            "id": 2,
            "kind": "weapon",
            "symbol": "wpn_m_submachinegun_kinetic_fauto",
            "name": "Karma C-44",
            "class": 1,
        },
    ]


def test_moves_to_the_player_s_carrier(service: EngineeringService) -> None:
    locker = {"event": "ShipLocker", "Items": [], "Components": [], "Consumables": [], "Data": []}
    part = on_foot(
        service,
        {"event": "CarrierLocation", "CarrierType": "FleetCarrier", "CarrierID": 7},
        {**locker, "Items": [{"Name": "gmeds", "Name_Localised": "Traitement", "Count": 4}]},
        {"event": "Docked", "StationType": "FleetCarrier", "MarketID": 7},
        locker,
    )
    assert part["carrierMoves"] == [
        {
            "dockedAt": T0,
            "at": T0,
            "materials": [{"symbol": "gmeds", "name": "Traitement", "count": -4}],
        }
    ]
