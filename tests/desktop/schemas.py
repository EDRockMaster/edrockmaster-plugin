"""Where the JSON schemas of the core's answers to the interface are (ADR 0020)."""

from pathlib import Path

import edrockmaster.desktop

SCHEMAS = Path(edrockmaster.desktop.__file__).with_name("schemas")
LIVE_VIEW_SCHEMA = SCHEMAS / "live_view.schema.json"
