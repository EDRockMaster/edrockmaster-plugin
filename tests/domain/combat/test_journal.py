from datetime import UTC, datetime

import pytest

from edrockmaster.domain.combat.journal import (
    BountyAwarded,
    CombatBondAwarded,
    CommanderDied,
    CommunityGoal,
    CommunityGoalsUpdated,
    CrimeCommitted,
    DestinationDropped,
    Embarked,
    FactionReward,
    GameClosed,
    GameLoaded,
    MiningSeen,
    NormalSpaceEntered,
    OnFootArrived,
    SettlementApproached,
    SiteLeft,
    VoucherKind,
    VouchersRedeemed,
    faction_name,
    parse_entry,
)
from edrockmaster.domain.combat.sites import SiteType

TS = "2026-10-03T21:00:00Z"
AT = datetime(2026, 10, 3, 21, 0, tzinfo=UTC)


def test_ship_bounty_is_parsed() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "Bounty",
            "Rewards": [
                {"Faction": "Federation", "Reward": 120000},
                {"Faction": "Sirius Corporation", "Reward": 30500},
            ],
            "Target": "empire_trader",
            "Target_Localised": "Imperial Clipper",
            "TotalReward": 150500,
            "VictimFaction": "Kumo Crew",
        }
    )
    assert fact == BountyAwarded(
        at=AT,
        total=150500,
        rewards=(FactionReward("Federation", 120000), FactionReward("Sirius Corporation", 30500)),
        target="Imperial Clipper",
        victim_faction="Kumo Crew",
        shared=False,
    )


def test_shared_bounty_is_flagged() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "Bounty",
            "Rewards": [{"Faction": "Federation", "Reward": 1000}],
            "TotalReward": 1000,
            "SharedWithOthers": 1,
        }
    )
    assert isinstance(fact, BountyAwarded)
    assert fact.shared
    assert fact.target is None


def test_single_faction_bounty_is_parsed() -> None:
    # Skimmers and on-foot targets use a flat format
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "Bounty",
            "Target": "Skimmer",
            "Faction": "$faction_Empire;",
            "Faction_Localised": "Empire",
            "Reward": 4500,
            "VictimFaction": "Raiders",
        }
    )
    assert fact == BountyAwarded(
        at=AT,
        total=4500,
        rewards=(FactionReward("Empire", 4500),),
        target="Skimmer",
        victim_faction="Raiders",
        shared=False,
    )


@pytest.mark.parametrize("event", ["FactionKillBond", "CapShipBond"])
def test_combat_bonds_are_parsed(event: str) -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": event,
            "Reward": 80000,
            "AwardingFaction": "$faction_Federation;",
            "AwardingFaction_Localised": "Federation",
            "VictimFaction": "Empire",
        }
    )
    assert fact == CombatBondAwarded(
        at=AT,
        amount=80000,
        awarding_faction="Federation",
        victim_faction="Empire",
        kill=event == "FactionKillBond",
    )


def test_bounty_vouchers_redeemed_are_parsed() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "RedeemVoucher",
            "Type": "bounty",
            "Amount": 150500,
            "Factions": [
                {"Faction": "Federation", "Amount": 120000},
                {"Faction": "Sirius Corporation", "Amount": 30500},
            ],
        }
    )
    assert fact == VouchersRedeemed(
        at=AT,
        kind=VoucherKind.BOUNTY,
        amount=150500,
        by_faction=(
            FactionReward("Federation", 120000),
            FactionReward("Sirius Corporation", 30500),
        ),
    )


def test_combat_bonds_redeemed_are_parsed() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "RedeemVoucher",
            "Type": "CombatBond",
            "Amount": 80000,
            "Faction": "Federation",
        }
    )
    assert fact == VouchersRedeemed(
        at=AT,
        kind=VoucherKind.COMBAT_BOND,
        amount=80000,
        by_faction=(FactionReward("Federation", 80000),),
    )


def test_other_vouchers_are_ignored() -> None:
    entry = {"timestamp": TS, "event": "RedeemVoucher", "Type": "codex", "Amount": 5000}
    assert parse_entry(entry) is None


def test_death_is_parsed() -> None:
    assert parse_entry({"timestamp": TS, "event": "Died", "KillerName": "x"}) == CommanderDied(AT)


@pytest.mark.parametrize("event", ["Shutdown", "ShutDown"])
def test_game_exit_is_parsed(event: str) -> None:
    assert parse_entry({"timestamp": TS, "event": event}) == GameClosed(AT)


def test_community_goals_are_parsed() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "CommunityGoal",
            "CurrentGoals": [
                {
                    "CGID": 812,
                    "Title": "Defend the Sirius Gate",
                    "SystemName": "Sirius",
                    "MarketName": "Patterson Enterprise",
                    "Expiry": "2026-10-08T06:00:00Z",
                    "IsComplete": False,
                    "CurrentTotal": 9876543210,
                    "PlayerContribution": 25000000,
                    "NumContributors": 4321,
                    "TopTier": {"Name": "Tier 8", "Bonus": ""},
                    "TopRankSize": 10,
                    "PlayerInTopRank": False,
                    "TierReached": "Tier 4",
                    "PlayerPercentileBand": 25,
                    "Bonus": 0,
                }
            ],
        }
    )
    assert fact == CommunityGoalsUpdated(
        at=AT,
        goals=(
            CommunityGoal(
                cgid=812,
                title="Defend the Sirius Gate",
                system="Sirius",
                expiry=datetime(2026, 10, 8, 6, 0, tzinfo=UTC),
                complete=False,
                contribution=25000000,
                percentile_band=25,
                tier_reached="Tier 4",
                top_tier="Tier 8",
            ),
        ),
    )


def test_community_goal_with_minimal_fields() -> None:
    fact = parse_entry(
        {
            "timestamp": TS,
            "event": "CommunityGoal",
            "CurrentGoals": [{"CGID": 1, "Title": "Goal", "PlayerContribution": 0}],
        }
    )
    assert isinstance(fact, CommunityGoalsUpdated)
    [goal] = fact.goals
    assert (goal.system, goal.expiry, goal.percentile_band, goal.tier_reached) == (
        None,
        None,
        None,
        None,
    )


@pytest.mark.parametrize(
    ("raw", "name"),
    [("$faction_Federation;", "Federation"), ("Sirius Corporation", "Sirius Corporation")],
)
def test_superpower_symbols_are_normalised(raw: str, name: str) -> None:
    assert faction_name(raw) == name


@pytest.mark.parametrize(
    "entry",
    [
        {"timestamp": TS, "event": "Bounty", "Rewards": "lots", "TotalReward": 1},
        {"timestamp": TS, "event": "Bounty", "Target": "x"},
        {"timestamp": TS, "event": "FactionKillBond", "Reward": "1"},
        {"timestamp": TS, "event": "RedeemVoucher", "Type": "bounty"},
        {"timestamp": TS, "event": "CommunityGoal", "CurrentGoals": [{"Title": "x"}]},
        {
            "timestamp": TS,
            "event": "CommunityGoal",
            "CurrentGoals": [{"CGID": 1, "Title": "x", "Expiry": "soon"}],
        },
        {"timestamp": TS, "event": "Music", "MusicTrack": "Combat_Dogfight"},
        {"timestamp": TS, "event": "SupercruiseDestinationDrop"},
        {"timestamp": TS, "event": "CommitCrime", "CrimeType": "assault", "Fine": "100"},
        {"timestamp": TS, "event": "StartJump", "JumpType": "Supercruise"},
    ],
)
def test_irrelevant_or_malformed_entries_are_ignored(entry: dict[str, object]) -> None:
    assert parse_entry(entry) is None


# --- places -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("signal", "site"),
    [
        ("$Warzone_PointRace_High:#index=1;", SiteType.CONFLICT_ZONE_HIGH),
        ("$MULTIPLAYER_SCENARIO79_TITLE;", SiteType.RES_HAZARDOUS),
        ("Tan Depot", None),
    ],
)
def test_supercruise_destination_drop_tells_the_site(signal: str, site: SiteType | None) -> None:
    entry = {"timestamp": TS, "event": "SupercruiseDestinationDrop", "Type": signal, "Threat": 4}
    assert parse_entry(entry) == DestinationDropped(AT, site)


@pytest.mark.parametrize(
    ("event", "body_type"),
    [("SupercruiseExit", "PlanetaryRing"), ("SupercruiseExit", "Station"), ("Undocked", None)],
)
def test_arriving_in_normal_space(event: str, body_type: str | None) -> None:
    entry = {"timestamp": TS, "event": event, "BodyType": body_type}
    assert parse_entry(entry) == NormalSpaceEntered(AT)


@pytest.mark.parametrize(
    ("event", "docked"),
    [("Location", False), ("StartUp", False), ("Location", True), ("StartUp", True)],
)
def test_game_loaded_tells_whether_docked(event: str, docked: bool) -> None:
    entry = {"timestamp": TS, "event": event, "Docked": docked, "BodyType": "Planet"}
    assert parse_entry(entry) == GameLoaded(AT, docked=docked)


def test_game_loaded_tells_whether_on_foot() -> None:
    entry = {"timestamp": TS, "event": "Location", "Docked": False, "OnFoot": True}
    assert parse_entry(entry) == GameLoaded(AT, docked=False, on_foot=True)


@pytest.mark.parametrize(
    "entry",
    [
        {"timestamp": TS, "event": "SupercruiseEntry"},
        {"timestamp": TS, "event": "Docked"},
        {"timestamp": TS, "event": "FSDJump"},
        {"timestamp": TS, "event": "StartJump", "JumpType": "Hyperspace"},
        {"timestamp": TS, "event": "BookDropship", "Retreat": True, "Cost": 0},
    ],
)
def test_leaving_normal_space_leaves_the_site(entry: dict[str, object]) -> None:
    assert parse_entry(entry) == SiteLeft(AT)


@pytest.mark.parametrize(
    "entry",
    [
        {"timestamp": TS, "event": "ProspectedAsteroid", "Materials": []},
        {"timestamp": TS, "event": "MiningRefined", "Type": "$painite_name;"},
        {"timestamp": TS, "event": "AsteroidCracked", "Body": "X"},
        {"timestamp": TS, "event": "LaunchDrone", "Type": "Prospector"},
        {"timestamp": TS, "event": "LaunchDrone", "Type": "Collection"},
    ],
)
def test_mining_is_seen(entry: dict[str, object]) -> None:
    assert parse_entry(entry) == MiningSeen(AT)


def test_dropship_to_a_conflict_zone_is_not_a_departure() -> None:
    entry = {"timestamp": TS, "event": "BookDropship", "Retreat": False, "Cost": 0}
    assert parse_entry(entry) is None


def test_dropship_deploy_is_an_arrival_on_foot() -> None:
    entry = {"timestamp": TS, "event": "DropshipDeploy", "OnPlanet": True, "OnStation": False}
    assert parse_entry(entry) == OnFootArrived(AT, dropship=True)


def test_disembarking_on_a_planet_is_an_arrival_on_foot() -> None:
    entry = {"timestamp": TS, "event": "Disembark", "SRV": False, "OnPlanet": True}
    assert parse_entry(entry) == OnFootArrived(AT, dropship=False)


@pytest.mark.parametrize(
    "entry",
    [
        {"timestamp": TS, "event": "Disembark", "OnStation": True, "OnPlanet": False},
        {"timestamp": TS, "event": "Disembark", "OnStation": False, "OnPlanet": False},
        {"timestamp": TS, "event": "Disembark", "OnStation": True, "OnPlanet": True},
    ],
)
def test_disembarking_elsewhere_is_no_arrival(entry: dict[str, object]) -> None:
    assert parse_entry(entry) is None


@pytest.mark.parametrize("on_station", [True, False])
def test_embarking_is_parsed(on_station: bool) -> None:
    entry = {"timestamp": TS, "event": "Embark", "Taxi": True, "OnStation": on_station}
    assert parse_entry(entry) == Embarked(AT, on_station=on_station)


def test_settlement_approached_is_parsed() -> None:
    entry = {
        "timestamp": TS,
        "event": "ApproachSettlement",
        "Name": "$Ancient:#index=1;",
        "Name_Localised": "Ancient Ruins",
    }
    assert parse_entry(entry) == SettlementApproached(AT, "Ancient Ruins")


def test_other_limpets_are_not_mining() -> None:
    assert parse_entry({"timestamp": TS, "event": "LaunchDrone", "Type": "Repair"}) is None


# --- crimes -------------------------------------------------------------------------------


def test_fine_is_parsed() -> None:
    entry = {
        "timestamp": TS,
        "event": "CommitCrime",
        "CrimeType": "recklessWeaponsDischarge",
        "Faction": "Iyakajauja Law Party",
        "Fine": 100,
    }
    assert parse_entry(entry) == CrimeCommitted(
        AT, kind="recklessWeaponsDischarge", fine=100, bounty=0
    )


def test_bounty_on_the_commander_is_parsed() -> None:
    entry = {
        "timestamp": TS,
        "event": "CommitCrime",
        "CrimeType": "murder",
        "Faction": "Federation",
        "Victim": "Somebody",
        "Bounty": 2_000,
    }
    assert parse_entry(entry) == CrimeCommitted(AT, kind="murder", fine=0, bounty=2_000)
