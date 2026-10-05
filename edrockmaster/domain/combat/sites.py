"""Combat sites, as the game names them on arrival (ADR 0013).

``SupercruiseDestinationDrop`` gives the type of the destination; the scan of
a system (``FSSSignalDiscovered``) uses the same identifiers. Only identifiers
confirmed on a real recording are listed: any other destination is not a
combat site, and its kills go to miscellaneous, unless a combat bond tells it
is a conflict zone (ADR 0015).
"""

from __future__ import annotations

from enum import Enum


class SiteType(Enum):
    CONFLICT_ZONE_LOW = "conflict_zone_low"
    CONFLICT_ZONE_MEDIUM = "conflict_zone_medium"
    CONFLICT_ZONE_HIGH = "conflict_zone_high"
    RES_LOW = "res_low"
    RES = "res"
    RES_HIGH = "res_high"
    RES_HAZARDOUS = "res_hazardous"
    NAV_BEACON = "nav_beacon"
    CONFLICT_ZONE_UNKNOWN = "conflict_zone_unknown"
    """A combat bond after a drop the journal did not name (ADR 0015)."""
    GROUND_CONFLICT_ZONE = "ground_conflict_zone"
    """On foot, reached by the dropship or told by a combat bond; no intensity (ADR 0015)."""
    UNKNOWN = "unknown"
    """A reward on a site the plugin did not see the commander arrive at (EDMC started there)."""


_SIGNALS = {
    "$warzone_pointrace_low": SiteType.CONFLICT_ZONE_LOW,
    "$warzone_pointrace_med": SiteType.CONFLICT_ZONE_MEDIUM,
    "$warzone_pointrace_high": SiteType.CONFLICT_ZONE_HIGH,
    "$multiplayer_scenario77_title": SiteType.RES_LOW,
    "$multiplayer_scenario14_title": SiteType.RES,
    "$multiplayer_scenario78_title": SiteType.RES_HIGH,
    "$multiplayer_scenario79_title": SiteType.RES_HAZARDOUS,
    "$multiplayer_scenario42_title": SiteType.NAV_BEACON,
}


def combat_site(signal: str) -> SiteType | None:
    """The combat site a destination type names (``$Warzone_PointRace_High:#index=1;``)."""
    return _SIGNALS.get(signal.split(":", 1)[0].removesuffix(";").lower())
