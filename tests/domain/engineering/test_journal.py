from datetime import UTC, datetime

import pytest

from edrockmaster.domain.engineering.journal import (
    BlueprintApplied,
    ChangeCause,
    EngineerProgressed,
    EngineersStated,
    EngineerState,
    EngineerStatus,
    GameClosed,
    InventoryStated,
    MaterialChange,
    MaterialsChanged,
    parse_entry,
)
from edrockmaster.domain.journal_reading import Entry

AT = datetime(2026, 10, 8, 5, 30, 26, tzinfo=UTC)
TS = "2026-10-08T05:30:26Z"


def changed(cause: ChangeCause, *changes: MaterialChange) -> MaterialsChanged:
    return MaterialsChanged(AT, cause, changes)


def test_the_inventory_the_game_states_at_load() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "Materials",
            "Raw": [{"Name": "sulphur", "Name_Localised": "Soufre", "Count": 299}],
            "Manufactured": [
                {
                    "Name": "protolightalloys",
                    "Name_Localised": "Proto-alliages légers",
                    "Count": 107,
                }
            ],
            "Encoded": [{"Name": "ShieldDensityReports", "Count": 3}],
        }
    )
    assert fact == InventoryStated(
        AT,
        (
            MaterialChange("sulphur", 299, "Soufre"),
            MaterialChange("protolightalloys", 107, "Proto-alliages légers"),
            MaterialChange("shielddensityreports", 3),
        ),
    )


@pytest.mark.parametrize(
    ("entry", "fact"),
    [
        (
            {
                "event": "MaterialCollected",
                "Category": "Manufactured",
                "Name": "focuscrystals",
                "Name_Localised": "Cristaux de focalisation",
                "Count": 3,
            },
            changed(
                ChangeCause.COLLECTED,
                MaterialChange("focuscrystals", 3, "Cristaux de focalisation"),
            ),
        ),
        (
            {"event": "MaterialDiscarded", "Category": "Raw", "Name": "iron", "Count": 12},
            changed(ChangeCause.DISCARDED, MaterialChange("iron", -12)),
        ),
        (
            {
                "event": "MaterialTrade",
                "MarketID": 3221524992,
                "TraderType": "manufactured",
                "Paid": {
                    "Material": "heatdispersionplate",
                    "Category": "Manufactured",
                    "Quantity": 6,
                },
                "Received": {
                    "Material": "heatexchangers",
                    "Category": "Manufactured",
                    "Quantity": 1,
                },
            },
            changed(
                ChangeCause.TRADED,
                MaterialChange("heatdispersionplate", -6),
                MaterialChange("heatexchangers", 1),
            ),
        ),
        (
            {
                "event": "Synthesis",
                "Name": "FSD Basic",
                "Materials": [{"Name": "carbon", "Count": 1}, {"Name": "vanadium", "Count": 1}],
            },
            changed(
                ChangeCause.SYNTHESISED,
                MaterialChange("carbon", -1),
                MaterialChange("vanadium", -1),
            ),
        ),
        (
            {
                "event": "TechnologyBroker",
                "BrokerType": "guardian",
                "Commodities": [{"Name": "powergridassembly", "Count": 1}],
                "Materials": [
                    {"Name": "guardian_powercell", "Count": 5, "Category": "Manufactured"}
                ],
            },
            changed(ChangeCause.BROKER, MaterialChange("guardian_powercell", -5)),
        ),
        (
            {
                "event": "EngineerContribution",
                "Engineer": "Marco Qwent",
                "EngineerID": 300200,
                "Type": "Materials",
                "Material": "modularterminals",
                "Quantity": 25,
                "TotalQuantity": 25,
            },
            changed(ChangeCause.CONTRIBUTED, MaterialChange("modularterminals", -25)),
        ),
        (
            {"event": "ScientificResearch", "Name": "nickel", "Category": "Raw", "Count": 5},
            changed(ChangeCause.RESEARCH, MaterialChange("nickel", -5)),
        ),
        (
            {
                "event": "MissionCompleted",
                "MaterialsReward": [
                    {"Name": "polonium", "Category": "$MICRORESOURCE_CATEGORY_Raw;", "Count": 3}
                ],
            },
            changed(ChangeCause.REWARDED, MaterialChange("polonium", 3)),
        ),
        ({"event": "Shutdown"}, GameClosed(AT)),
    ],
)
def test_material_changes(entry: Entry, fact: object) -> None:
    assert parse_entry({"timestamp": TS, **entry}) == fact


@pytest.mark.parametrize(
    "entry",
    [
        {"event": "EngineerContribution", "Type": "Commodity", "Commodity": "gold", "Quantity": 1},
        {"event": "MissionCompleted", "Reward": 100000},
        {"event": "TechnologyBroker", "BrokerType": "human"},
        {"event": "MaterialCollected", "Name": "iron", "Count": -1},
        {"event": "MaterialCollected", "Name": " ", "Count": 1},
        {"event": "EngineerCraft", "BlueprintName": "FSD_LongRange", "Level": 6},
        {"event": "Music", "MusicTrack": "Exploration"},
    ],
)
def test_irrelevant_or_malformed_entries_are_ignored(entry: Entry) -> None:
    assert parse_entry({"timestamp": TS, **entry}) is None


def test_a_blueprint_roll() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "EngineerCraft",
            "Slot": "PowerDistributor",
            "Module": "int_powerdistributor_size7_class5",
            "Ingredients": [{"Name": "sulphur", "Name_Localised": "Soufre", "Count": 1}],
            "Engineer": "Marco Qwent",
            "EngineerID": 300200,
            "BlueprintID": 128673730,
            "BlueprintName": "PowerDistributor_HighCapacity",
            "Level": 1,
            "Quality": 0.5,
        }
    )
    assert fact == BlueprintApplied(
        AT,
        "PowerDistributor_HighCapacity",
        1,
        "int_powerdistributor_size7_class5",
        300200,
        None,
        (MaterialChange("sulphur", -1, "Soufre"),),
    )


def test_an_experimental_effect() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "EngineerCraft",
            "Module": "int_hyperdrive_size5_class5",
            "Ingredients": [{"Name": "arsenic", "Count": 5}],
            "BlueprintName": "FSD_LongRange",
            "Level": 5,
            "ApplyExperimentalEffect": "special_fsd_heavy",
        }
    )
    assert isinstance(fact, BlueprintApplied)
    assert fact.effect == "special_fsd_heavy"
    assert fact.engineer_id is None


def test_every_engineer_at_load_then_one_change() -> None:
    stated = parse_entry(
        {
            "timestamp": TS,
            "event": "EngineerProgress",
            "Engineers": [
                {
                    "Engineer": "Felicity Farseer",
                    "EngineerID": 300100,
                    "Progress": "Unlocked",
                    "RankProgress": 0,
                    "Rank": 5,
                },
                {"Engineer": "Etienne Dorn", "EngineerID": 300290, "Progress": "Invited"},
            ],
        }
    )
    assert stated == EngineersStated(
        AT,
        (
            EngineerState(300100, "Felicity Farseer", EngineerStatus.UNLOCKED, 5),
            EngineerState(300290, "Etienne Dorn", EngineerStatus.INVITED),
        ),
    )
    progressed = parse_entry(
        {
            "timestamp": TS,
            "event": "EngineerProgress",
            "Engineer": "Etienne Dorn",
            "EngineerID": 300290,
            "Progress": "Unlocked",
            "Rank": 1,
        }
    )
    assert progressed == EngineerProgressed(
        AT, EngineerState(300290, "Etienne Dorn", EngineerStatus.UNLOCKED, 1)
    )


def test_an_unknown_engineer_status_is_malformed() -> None:
    entry = {
        "timestamp": TS,
        "event": "EngineerProgress",
        "Engineer": "Etienne Dorn",
        "EngineerID": 300290,
        "Progress": "Befriended",
    }
    assert parse_entry(entry) is None
