from datetime import UTC, datetime

import pytest

from edrockmaster.domain.bounty.journal import (
    BountyAwarded,
    CombatBondAwarded,
    CommanderDied,
    CommunityGoal,
    CommunityGoalsUpdated,
    FactionReward,
    GameClosed,
    SiteEntered,
    SiteLeft,
    VoucherKind,
    VouchersRedeemed,
    faction_name,
    parse_entry,
)

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
        {"timestamp": TS, "event": "MiningRefined", "Type": "painite"},
    ],
)
def test_irrelevant_or_malformed_entries_are_ignored(entry: dict[str, object]) -> None:
    assert parse_entry(entry) is None


# --- combat sites -------------------------------------------------------------------------


@pytest.mark.parametrize("body_type", ["Planet", "PlanetaryRing", "Star", "Null"])
def test_dropping_out_of_supercruise_away_from_a_station_enters_a_site(body_type: str) -> None:
    entry = {"timestamp": TS, "event": "SupercruiseExit", "Body": "X", "BodyType": body_type}
    assert parse_entry(entry) == SiteEntered(AT)


def test_dropping_at_a_station_is_not_a_site() -> None:
    entry = {"timestamp": TS, "event": "SupercruiseExit", "Body": "X", "BodyType": "Station"}
    assert parse_entry(entry) is None


def test_game_loaded_in_normal_space_away_from_a_station_is_a_site() -> None:
    entry = {"timestamp": TS, "event": "Location", "Docked": False, "BodyType": "Planet"}
    assert parse_entry(entry) == SiteEntered(AT)


@pytest.mark.parametrize(
    "entry",
    [
        {"timestamp": TS, "event": "Location", "Docked": True, "BodyType": "Station"},
        {"timestamp": TS, "event": "Location", "Docked": False, "BodyType": "Station"},
        {"timestamp": TS, "event": "Location", "Docked": False},
    ],
)
def test_other_locations_are_not_sites(entry: dict[str, object]) -> None:
    assert parse_entry(entry) is None


@pytest.mark.parametrize("event", ["SupercruiseEntry", "Docked", "FSDJump"])
def test_leaving_normal_space_leaves_the_site(event: str) -> None:
    assert parse_entry({"timestamp": TS, "event": event}) == SiteLeft(AT)
