"""The live view the core pushes to the interface (ADR 0020), as ``live_view.schema.json`` says.

The blocks come from the plugin's presenters: their texts are already in the
player's language. The interface's own texts (titles, the notice, the journal
status) come from its catalogues, in the same language (ADR 0021).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from edrockmaster.ui.panel_model import ActivityBlock, LocalDataNotice

VERSION = 1
SCHEMA = Path(__file__).with_name("schemas") / "live_view.schema.json"


def live_view(  # noqa: PLR0913 - one argument per part of the view
    *,
    language: str,
    current: str,
    blocks: tuple[ActivityBlock, ...],
    notice: LocalDataNotice | None,
    journal_folder: Path | None,
    journal_file: Path | None,
) -> dict[str, Any]:
    return {
        "version": VERSION,
        "language": language,
        "current": current,
        "activities": [
            {
                "activity": block.activity.value,
                "status": block.model.status,
                "lines": [{"label": line.label, "value": line.value} for line in block.model.lines],
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
    }
