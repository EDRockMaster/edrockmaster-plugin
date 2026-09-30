from mining.session import MiningSession


def test_counts_refined_and_drones() -> None:
    s = MiningSession()
    s.handle({"event": "LaunchDrone", "Type": "Prospector"})
    s.handle({"event": "ProspectedAsteroid", "Content": "$AsteroidMaterialContent_High;"})
    s.handle({"event": "MiningRefined", "Type": "$platinum_name;"})
    s.handle({"event": "MiningRefined", "Type": "$platinum_name;"})
    assert s.prospected == 1
    assert s.refined["$platinum_name;"] == 2
    assert s.limpets_launched["Prospector"] == 1
