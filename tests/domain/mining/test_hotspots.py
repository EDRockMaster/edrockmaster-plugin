from datetime import UTC, datetime

import pytest

from edrockmaster.domain.mining.hotspots import (
    HOTSPOT_COMMODITIES,
    PAGE_SIZE,
    HotspotQuery,
    ReserveLevel,
    Ring,
    hotspot_commodity,
)

PAINITE = hotspot_commodity("Painite")


def test_hotspots_exist_for_thirteen_commodities() -> None:
    assert len(HOTSPOT_COMMODITIES) == 13
    assert len({commodity.key for commodity in HOTSPOT_COMMODITIES}) == 13


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Painite", "painite"),
        ("painite", "painite"),
        ("$painite_name;", "painite"),
        ("Low Temperature Diamonds", "lowtemperaturediamond"),
        ("LowTemperatureDiamond", "lowtemperaturediamond"),
        ("lowtemperaturediamond", "lowtemperaturediamond"),
        ("Void Opal", "opal"),
        ("Opal", "opal"),
        ("Platinum", "platinum"),
    ],
)
def test_every_source_s_name_of_a_hotspot_commodity_is_known(name: str, key: str) -> None:
    commodity = hotspot_commodity(name)
    assert commodity is not None
    assert commodity.key == key


def test_a_commodity_without_hotspots_is_not_one() -> None:
    assert hotspot_commodity("Gold") is None
    assert hotspot_commodity("") is None


def test_the_english_name_is_the_game_s() -> None:
    names = {commodity.key: commodity.english for commodity in HOTSPOT_COMMODITIES}
    assert names["lowtemperaturediamond"] == "Low Temperature Diamonds"
    assert names["opal"] == "Void Opal"


def test_a_query_keeps_its_bounds() -> None:
    assert PAINITE is not None
    query = HotspotQuery(PAINITE, "Borann")
    assert (query.minimum_count, query.reserves, query.max_distance, query.page) == (
        1,
        frozenset(),
        50.0,
        0,
    )
    with pytest.raises(ValueError, match="system"):
        HotspotQuery(PAINITE, "  ")
    with pytest.raises(ValueError, match="hotspot"):
        HotspotQuery(PAINITE, "Borann", minimum_count=0)
    with pytest.raises(ValueError, match="distance"):
        HotspotQuery(PAINITE, "Borann", max_distance=0)
    with pytest.raises(ValueError, match="page"):
        HotspotQuery(PAINITE, "Borann", page=-1)
    assert HotspotQuery(PAINITE, " Borann ").reference == "Borann"
    assert PAGE_SIZE == 10


def test_a_ring_counts_the_hotspots_of_a_commodity() -> None:
    assert PAINITE is not None
    ring = Ring(
        system="Borann",
        body="Borann A 2",
        name="Borann A 2 A Ring",
        ring_type="Metal Rich",
        reserve=ReserveLevel.PRISTINE,
        hotspots=(("painite", 10), ("platinum", 3)),
        distance=0.0,
        arrival=901.7,
        seen=datetime(2022, 6, 17, 1, 31, 28, tzinfo=UTC),
    )
    assert ring.count(PAINITE) == 10
    platinum = hotspot_commodity("Platinum")
    tritium = hotspot_commodity("Tritium")
    assert platinum is not None
    assert tritium is not None
    assert ring.count(platinum) == 3
    assert ring.count(tritium) == 0


def test_reserve_levels_by_their_source_name() -> None:
    assert ReserveLevel.from_name("Pristine") is ReserveLevel.PRISTINE
    assert ReserveLevel.from_name("depleted") is ReserveLevel.DEPLETED
    assert ReserveLevel.from_name("") is None
    assert ReserveLevel.from_name(None) is None
    assert ReserveLevel.from_name("Bottomless") is None
