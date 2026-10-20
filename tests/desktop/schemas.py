"""Where the JSON schemas of the core's answers to the interface are (ADR 0020)."""

import json
from pathlib import Path
from typing import Any

import jsonschema
from referencing import Registry, Resource

import edrockmaster.desktop

SCHEMAS = Path(edrockmaster.desktop.__file__).with_name("schemas")
LIVE_VIEW_SCHEMA = SCHEMAS / "live_view.schema.json"


def validate(schema: str, definition: str, view: Any) -> Any:
    """``view`` against a definition of ``<schema>.schema.json``, whose references to the other
    schemas (``markets.schema.json#/$defs/MarketOffer``) resolve to them."""
    resources = [
        (document["$id"], Resource.from_contents(document))
        for path in SCHEMAS.glob("*.schema.json")
        for document in (json.loads(path.read_text(encoding="utf-8")),)
    ]
    root = json.loads((SCHEMAS / f"{schema}.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(
        {**root, "$ref": f"#/$defs/{definition}"}, registry=Registry().with_resources(resources)
    ).validate(view)
    return view
