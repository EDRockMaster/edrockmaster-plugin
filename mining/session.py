"""État d'une session de minage, alimenté par les événements du journal."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MiningSession:
    prospected: int = 0
    refined: Counter[str] = field(default_factory=Counter)
    limpets_launched: Counter[str] = field(default_factory=Counter)
    cracked: int = 0

    def handle(self, entry: dict[str, Any]) -> None:
        match entry.get("event"):
            case "ProspectedAsteroid":
                self.prospected += 1
            case "MiningRefined":
                self.refined[entry["Type"]] += 1
            case "LaunchDrone":
                self.limpets_launched[entry["Type"]] += 1
            case "AsteroidCracked":
                self.cracked += 1
