"""Raw journal entries for tests, as the game writes them."""

from datetime import UTC, datetime, timedelta

from edrockmaster.domain.journal_reading import Entry

T0 = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def timestamp(minutes: float) -> str:
    return (T0 + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def ring_entry(minutes: float = 0) -> Entry:
    return {
        "timestamp": timestamp(minutes),
        "event": "SupercruiseExit",
        "StarSystem": "Col 285 Sector AB-C d1",
        "SystemAddress": 42,
        "Body": "Col 285 Sector AB-C d1 2 A Ring",
        "BodyType": "PlanetaryRing",
    }


def prospected_entry(
    minutes: float,
    painite: float = 30.0,
    content: str = "$AsteroidMaterialContent_High;",
    motherlode: str | None = None,
) -> Entry:
    entry: dict[str, object] = {
        "timestamp": timestamp(minutes),
        "event": "ProspectedAsteroid",
        "Materials": [
            {"Name": "Painite", "Proportion": painite},
            {"Name": "Bromellite", "Proportion": 100.0 - painite},
        ],
        "Content": content,
        "Remaining": 100.0,
    }
    if motherlode is not None:
        entry["MotherlodeMaterial"] = motherlode
    return entry


def refined_entry(minutes: float, commodity: str = "$painite_name;") -> Entry:
    return {
        "timestamp": timestamp(minutes),
        "event": "MiningRefined",
        "Type": commodity,
        "Type_Localised": "Painite",
    }


def supercruise_entry(minutes: float) -> Entry:
    return {"timestamp": timestamp(minutes), "event": "SupercruiseEntry", "StarSystem": "Col 285"}


def bounty_entry(minutes: float, reward: int = 100_000, faction: str = "Federation") -> Entry:
    return {
        "timestamp": timestamp(minutes),
        "event": "Bounty",
        "Rewards": [{"Faction": faction, "Reward": reward}],
        "Target": "anaconda",
        "Target_Localised": "Anaconda",
        "TotalReward": reward,
        "VictimFaction": "Pirates",
    }


def redeem_entry(minutes: float, amount: int, faction: str = "Federation") -> Entry:
    return {
        "timestamp": timestamp(minutes),
        "event": "RedeemVoucher",
        "Type": "bounty",
        "Amount": amount,
        "Factions": [{"Faction": faction, "Amount": amount}],
    }


def community_goal_entry(minutes: float, contribution: int = 25_000_000) -> Entry:
    return {
        "timestamp": timestamp(minutes),
        "event": "CommunityGoal",
        "CurrentGoals": [
            {
                "CGID": 812,
                "Title": "Defend the Sirius Gate",
                "SystemName": "Sirius",
                "Expiry": "2026-10-08T06:00:00Z",
                "IsComplete": False,
                "PlayerContribution": contribution,
                "PlayerPercentileBand": 25,
                "TierReached": "Tier 4",
                "TopTier": {"Name": "Tier 8", "Bonus": ""},
            }
        ],
    }


def market_buy_entry(
    minutes: float, commodity: str = "palladium", count: int = 100, price: int = 5_000
) -> Entry:
    return {
        "timestamp": timestamp(minutes),
        "event": "MarketBuy",
        "MarketID": 4300769795,
        "Type": commodity,
        "Count": count,
        "BuyPrice": price,
        "TotalCost": count * price,
    }
