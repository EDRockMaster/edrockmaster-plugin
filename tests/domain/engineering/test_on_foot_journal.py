from datetime import UTC, datetime

import pytest

from edrockmaster.domain.engineering.catalogue import OnFootKind
from edrockmaster.domain.engineering.journal import CommanderDied, parse_entry
from edrockmaster.domain.engineering.on_foot_journal import (
    BackpackChanged,
    BackpackStated,
    Boarded,
    EquipmentSold,
    LoadoutChosen,
    LockerStated,
    Stock,
    Suit,
    SuitBought,
    Weapon,
    WeaponBought,
    WeaponEquipped,
)
from edrockmaster.domain.journal_reading import Entry

AT = datetime(2026, 10, 5, 21, 27, 6, tzinfo=UTC)
TS = "2026-10-05T21:27:06Z"


def entry(event: str, **fields: object) -> Entry:
    return {"timestamp": TS, "event": event, **fields}


def test_the_whole_ship_locker() -> None:
    fact = parse_entry(
        entry(
            "ShipLocker",
            Items=[
                {
                    "Name": "chemicalsample",
                    "Name_Localised": "Échantillon chimique",
                    "OwnerID": 0,
                    "Count": 2,
                },
                # Stolen: OwnerID is the owner it was taken from; it is the player's all the same
                {"Name": "gmeds", "OwnerID": 2954036037, "Count": 1},
                {"Name": "insight", "OwnerID": 0, "MissionID": 1012345678, "Count": 1},
            ],
            Components=[{"Name": "Graphene", "OwnerID": 0, "Count": 4}],
            Consumables=[
                {"Name": "healthpack", "Name_Localised": "Médikit", "OwnerID": 0, "Count": 99}
            ],
            Data=[{"Name": "internalcorrespondence", "OwnerID": 0, "Count": 3}],
        )
    )
    assert fact == LockerStated(
        AT,
        (
            Stock("chemicalsample", OnFootKind.ITEM, 2, "Échantillon chimique"),
            Stock("gmeds", OnFootKind.ITEM, 1),
            Stock("insight", OnFootKind.ITEM, 1, mission=True),
            Stock("graphene", OnFootKind.COMPONENT, 4),
            Stock("internalcorrespondence", OnFootKind.DATA, 3),
            Stock("healthpack", OnFootKind.CONSUMABLE, 99, "Médikit"),
        ),
    )


def test_a_ship_locker_without_content_only_points_to_its_file() -> None:
    # ShipLocker.json then holds the same content as the last full event: nothing new
    assert parse_entry(entry("ShipLocker")) is None


def test_the_whole_backpack() -> None:
    fact = parse_entry(
        entry(
            "Backpack",
            Items=[],
            Components=[{"Name": "ionbattery", "OwnerID": 0, "Count": 1}],
            Consumables=[],
            Data=[],
        )
    )
    assert fact == BackpackStated(AT, (Stock("ionbattery", OnFootKind.COMPONENT, 1),))


def test_a_change_of_the_backpack() -> None:
    fact = parse_entry(
        entry(
            "BackpackChange",
            Added=[
                {
                    "Name": "ionbattery",
                    "Name_Localised": "Batterie ionique",
                    "OwnerID": 0,
                    "Count": 1,
                    "Type": "Component",
                },
                {"Name": "factionnews", "OwnerID": 0, "Count": 2, "Type": "Data"},
            ],
            Removed=[{"Name": "amm_grenade_frag", "OwnerID": 0, "Count": 1, "Type": "Consumable"}],
        )
    )
    assert fact == BackpackChanged(
        AT,
        added=(
            Stock("ionbattery", OnFootKind.COMPONENT, 1, "Batterie ionique"),
            Stock("factionnews", OnFootKind.DATA, 2),
        ),
        removed=(Stock("amm_grenade_frag", OnFootKind.CONSUMABLE, 1),),
    )


def test_boarding_a_ship_an_srv_or_a_taxi() -> None:
    fact = parse_entry(entry("Embark", SRV=True, Taxi=False, Multicrew=False))
    assert fact == Boarded(AT)


def test_a_death() -> None:
    assert parse_entry(entry("Died")) == CommanderDied(AT)


TORMENTOR = {
    "SlotName": "SecondaryWeapon",
    "SuitModuleID": 1700319560391861,
    "ModuleName": "wpn_s_pistol_plasma_charged",
    "ModuleName_Localised": "Manticore Tormentor",
    "Class": 1,
    "WeaponMods": [],
}


@pytest.mark.parametrize("event", ["SuitLoadout", "SwitchSuitLoadout", "CreateSuitLoadout"])
def test_the_suit_and_weapons_of_a_loadout(event: str) -> None:
    fact = parse_entry(
        entry(
            event,
            SuitID=1701757244975121,
            SuitName="tacticalsuit_class3",
            SuitName_Localised="$TacticalSuit_Class1_Name;",
            SuitMods=["suit_improvedradar"],
            LoadoutID=4293000003,
            LoadoutName="Config. 3",
            Modules=[
                {**TORMENTOR},
                {
                    "SlotName": "PrimaryWeapon1",
                    "SuitModuleID": 1878319875493998,
                    "ModuleName": "Wpn_M_SubMachineGun_Laser_FAuto",
                    "Class": 3,
                    "WeaponMods": ["weapon_handling"],
                },
            ],
        )
    )
    assert fact == LoadoutChosen(
        AT,
        Suit(1701757244975121, "tacticalsuit", 3, ("suit_improvedradar",)),
        (
            Weapon(1700319560391861, "wpn_s_pistol_plasma_charged", 1, (), "Manticore Tormentor"),
            Weapon(1878319875493998, "wpn_m_submachinegun_laser_fauto", 3, ("weapon_handling",)),
        ),
    )


def test_the_flight_suit_has_no_class() -> None:
    fact = parse_entry(
        entry(
            "SuitLoadout",
            SuitID=1700213111689697,
            SuitName="flightsuit",
            SuitMods=[],
            LoadoutID=4293000002,
            Modules=[],
        )
    )
    assert fact == LoadoutChosen(AT, Suit(1700213111689697, "flightsuit", None, ()), ())


def test_a_weapon_equipped_in_a_loadout() -> None:
    fact = parse_entry(
        entry(
            "LoadoutEquipModule",
            SuitID=1701757244975121,
            SuitName="tacticalsuit_class3",
            LoadoutID=4293000003,
            SlotName="PrimaryWeapon2",
            ModuleName="wpn_m_launcher_rocket_sauto",
            ModuleName_Localised="Karma L-6",
            Class=1,
            WeaponMods=[],
            SuitModuleID=1700217557383166,
        )
    )
    assert fact == WeaponEquipped(
        AT, Weapon(1700217557383166, "wpn_m_launcher_rocket_sauto", 1, (), "Karma L-6")
    )


def test_a_suit_and_a_weapon_bought_then_sold() -> None:
    assert parse_entry(
        entry(
            "BuySuit", Name="UtilitySuit_Class2", Price=750000, SuitID=1878178949341729, SuitMods=[]
        )
    ) == SuitBought(AT, Suit(1878178949341729, "utilitysuit", 2, ()))
    assert parse_entry(
        entry(
            "BuyWeapon",
            Name="Wpn_M_SubMachineGun_Laser_FAuto",
            Name_Localised="TK Eclipse",
            Class=3,
            Price=5625000,
            SuitModuleID=1878319875493998,
            WeaponMods=["weapon_handling"],
        )
    ) == WeaponBought(
        AT,
        Weapon(
            1878319875493998,
            "wpn_m_submachinegun_laser_fauto",
            3,
            ("weapon_handling",),
            "TK Eclipse",
        ),
    )
    assert parse_entry(
        entry(
            "SellWeapon",
            Name="wpn_m_submachinegun_laser_fauto",
            Class=1,
            WeaponMods=[],
            Price=45000,
            SuitModuleID=1700669212164319,
        )
    ) == EquipmentSold(AT, 1700669212164319)
    assert parse_entry(
        entry("SellSuit", Name="utilitysuit_class2", Price=10000, SuitID=1878178949341729)
    ) == EquipmentSold(AT, 1878178949341729)


@pytest.mark.parametrize(
    "malformed",
    [
        entry("ShipLocker", Items=[{"Name": "gmeds"}], Components=[], Consumables=[], Data=[]),
        entry(
            "ShipLocker",
            Items=[{"Name": "gmeds", "Count": -1}],
            Components=[],
            Consumables=[],
            Data=[],
        ),
        entry("BackpackChange", Added=[{"Name": "gmeds", "Count": 1, "Type": "Gadget"}]),
        entry("BuyWeapon", Name="wpn_x", Class=7, SuitModuleID=1, WeaponMods=[]),
        entry("SuitLoadout", SuitID=1, SuitName="tacticalsuit_class3", SuitMods=[], Modules="none"),
        entry("ShipLocker", Items=[{"Name": " ", "Count": 1}]),
        entry("BuySuit", Name="UtilitySuit_Class2", SuitID=1, SuitMods=[1]),
    ],
)
def test_a_malformed_on_foot_entry_is_ignored(malformed: Entry) -> None:
    assert parse_entry(malformed) is None
