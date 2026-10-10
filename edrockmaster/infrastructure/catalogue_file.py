"""Reads the engineering catalogue shipped with the application (ADR 0017)."""

from __future__ import annotations

import json
from pathlib import Path

from edrockmaster.domain.engineering import catalogue as catalogue_module
from edrockmaster.domain.engineering.catalogue import Catalogue

CATALOGUE_FILE = Path(catalogue_module.__file__).with_name("catalogue.json")


def load_catalogue(path: Path = CATALOGUE_FILE) -> Catalogue:
    """The catalogue in ``path``; raises ``CatalogueError`` if it is not what the code expects."""
    return Catalogue.from_data(json.loads(path.read_text(encoding="utf-8")))
