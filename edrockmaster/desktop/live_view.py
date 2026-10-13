"""The live view the core pushes to the interface (ADR 0020), as ``live_view.schema.json`` says.

The blocks come from the presenters: their texts are already in the
player's language. The interface's own texts (titles, the notice, the journal
status) come from its catalogues, in the same language (ADR 0021).
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from typing import Any

from edrockmaster.domain.situation.route import CurrentRoute, scoopable
from edrockmaster.domain.situation.situation import Situation
from edrockmaster.ui.panel_model import ActivityBlock, LocalDataNotice, StatLine

VERSION = 1


def live_view(  # noqa: PLR0913 - one argument per part of the view
    *,
    language: str,
    current: str,
    blocks: tuple[ActivityBlock, ...],
    notice: LocalDataNotice | None,
    journal_folder: Path | None,
    journal_file: Path | None,
    situation: Situation,
    engineering: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": VERSION,
        "language": language,
        "current": current,
        "activities": [
            {
                "activity": block.activity.value,
                "status": block.model.status,
                "lines": [_line(line) for line in block.model.lines],
                "alert": block.model.alert,
                "canReset": block.model.can_reset,
            }
            for block in blocks
        ],
        "notice": notice.value if notice else None,
        "journal": {
            "folder": str(journal_folder) if journal_folder else None,
            "file": journal_file.name if journal_file else None,
        },
        "situation": _situation(situation),
        "engineering": engineering,
    }


def _line(line: StatLine) -> dict[str, Any]:
    shown: dict[str, Any] = {"label": line.label, "value": line.value}
    if line.until is not None:
        shown["until"] = line.until.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return shown


def _situation(situation: Situation) -> dict[str, Any]:
    ship = situation.ship
    return {
        "commander": situation.commander,
        "ship": None
        if ship is None
        else {"type": ship.type_name or ship.symbol, "name": ship.name, "ident": ship.ident},
        "onFoot": situation.on_foot,
        "system": situation.system,
        "station": situation.station,
        "mode": situation.mode.value if situation.mode else None,
        "group": situation.group,
        "wing": list(situation.wing),
        "gameRunning": situation.game_running,
        "route": _route(situation.route) if situation.route else None,
    }


def _route(route: CurrentRoute) -> dict[str, Any]:
    following = route.next
    return {
        "destination": route.destination,
        "jumpsLeft": route.jumps_left,
        "offRoute": route.off_route,
        "next": None
        if following is None
        else {
            "system": following.system,
            "starClass": following.star_class,
            "scoopable": scoopable(following.star_class),
            "danger": danger.value if (danger := route.danger) else None,
        },
        "nextScoopableIn": route.next_scoopable_in,
        "fuelTight": route.fuel_tight,
    }
