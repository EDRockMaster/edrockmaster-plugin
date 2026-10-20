"""Import the commodities the game trades, by category, into the application (ADR 0047).

Reads EDCD/FDevIDs' ``commodity.csv`` and ``rare_commodity.csv`` at the commit the
engineering catalogue pins, and writes ``edrockmaster/domain/trade/commodities.json``:
each commodity's key (the journal's symbol in lower case), English name, category and
whether it is rare, with the commit it comes from. Limpets, which no market trades,
are left out.

The data is Frontier Developments' intellectual property (see ``NOTICE``).

Usage: python3 scripts/import_commodities.py [<commodities.json>]
"""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "edrockmaster/domain/trade/commodities.json"
NOT_TRADED = "NonMarketable"

type Read = Callable[[Any, str], str]


def _engineering_import() -> Any:
    """The engineering import, for its pinned FDevIDs commit and its reader."""
    spec = importlib.util.spec_from_file_location(
        "import_engineering_data", Path(__file__).with_name("import_engineering_data.py")
    )
    if spec is None or spec.loader is None:  # pragma: no cover - the file is beside this one
        raise ImportRefused("scripts/import_engineering_data.py is missing")
    module = importlib.util.module_from_spec(spec)
    # Its dataclasses look their module up while they are made
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


class ImportRefused(Exception):  # noqa: N818 - a refusal, not a programming error
    """The source holds what the script cannot take: nothing is written."""


def commodities(common: str, rare: str) -> list[dict[str, Any]]:
    """Each traded commodity, by key."""
    rows: dict[str, dict[str, Any]] = {}
    for text, is_rare in ((common, False), (rare, True)):
        for row in csv.DictReader(io.StringIO(text)):
            key, name = row["symbol"].strip().lower(), row["name"].strip()
            category = row["category"].strip()
            if not key or not name or not category:
                raise ImportRefused(f"a commodity without its symbol, name or category: {row!r}")
            if key in rows:
                raise ImportRefused(f"{key} is listed twice")
            if category != NOT_TRADED:
                rows[key] = {"key": key, "name": name, "category": category, "rare": is_rare}
    return [rows[key] for key in sorted(rows)]


def main(argv: list[str], read: Read | None = None) -> int:
    if len(argv) > 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    engineering = _engineering_import()
    output = Path(argv[1]) if len(argv) == 2 else DEFAULT_OUTPUT
    source = engineering.FDEVIDS
    fetch = read or engineering.read_github
    try:
        rows = commodities(fetch(source, "commodity.csv"), fetch(source, "rare_commodity.csv"))
    except ImportRefused as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 1
    lines = ",\n".join(f"    {json.dumps(row, ensure_ascii=False)}" for row in rows)
    origin = {"repository": source.repository, "commit": source.commit, "date": source.date}
    output.write_text(
        f'{{\n  "source": {json.dumps(origin)},\n  "commodities": [\n{lines}\n  ]\n}}\n',
        encoding="utf-8",
        newline="\n",
    )
    print(f"{output}: {len(rows)} commodities")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
