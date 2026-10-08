from collections import defaultdict
from datetime import UTC, datetime

from edrockmaster.domain.engineering.journal import (
    EngineersStated,
    EngineerState,
    EngineerStatus,
    InventoryStated,
    MaterialChange,
)
from edrockmaster.edmc.state import engineers_from_state, inventory_from_state
from tests.domain.engineering.catalogue_data import catalogue

AT = datetime(2026, 10, 8, 4, 0, tzinfo=UTC)


def test_the_inventory_edmc_knows() -> None:
    raw: defaultdict[str, int] = defaultdict(int, {"arsenic": 12, "iron": 0})
    state = {"Raw": raw, "Manufactured": {"chemicalmanipulators": 4}, "Encoded": {}}
    assert inventory_from_state(state, AT) == InventoryStated(
        AT, (MaterialChange("arsenic", 12), MaterialChange("chemicalmanipulators", 4))
    )


def test_an_empty_inventory_means_edmc_knows_none() -> None:
    assert inventory_from_state({"Raw": defaultdict(int), "Manufactured": None}, AT) is None
    assert inventory_from_state({}, AT) is None


def test_the_engineers_edmc_knows_by_name() -> None:
    state = {
        "Engineers": {
            "Felicity Farseer": (5, 0),
            "Jude Navarro": "Known",  # Odyssey: not in the catalogue
        }
    }
    assert engineers_from_state(state, catalogue(), AT) == EngineersStated(
        AT, (EngineerState(300100, "Felicity Farseer", EngineerStatus.UNLOCKED, 5),)
    )
    assert engineers_from_state(
        {"Engineers": {"Felicity Farseer": "Invited"}}, catalogue(), AT
    ) == (EngineersStated(AT, (EngineerState(300100, "Felicity Farseer", EngineerStatus.INVITED),)))


def test_engineers_edmc_cannot_tell() -> None:
    assert engineers_from_state({"Engineers": {}}, catalogue(), AT) is None
    assert (
        engineers_from_state({"Engineers": {"Felicity Farseer": "Befriended"}}, catalogue(), AT)
        is None
    )
    assert engineers_from_state({}, catalogue(), AT) is None
