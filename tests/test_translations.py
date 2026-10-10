"""Every displayed text has a French translation, and every translation is still used."""

import ast
import re
from pathlib import Path

from edrockmaster.infrastructure.catalogue_file import load_catalogue
from edrockmaster.ui import (
    combat_presenter,
    engineering_names,
    engineering_presenter,
    mining_presenter,
    trade_presenter,
)
from edrockmaster.ui.commodity_names import MINEABLE

ROOT = Path(__file__).resolve().parent.parent
SOURCES = sorted((ROOT / "edrockmaster").rglob("*.py"))
TRANSLATION = re.compile(r'^\s*"((?:[^"\\]|\\.)+)"\s*=\s*"((?:[^"\\]|\\.)+)"\s*;\s*$')
TRANSLATE_NAMES = {"tl", "_tl", "translate"}


def literal_calls(path: Path) -> set[str]:
    """String literals passed to ``tl()`` (or ``self._tl()``) in a source file."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        argument = node.args[0]
        if (
            name in TRANSLATE_NAMES
            and isinstance(argument, ast.Constant)
            and isinstance(argument.value, str)
        ):
            found.add(argument.value)
    return found


def source_strings() -> set[str]:
    strings = set().union(*(literal_calls(path) for path in SOURCES))
    # Texts translated through a variable: declared in tables
    strings |= {name for _, name in MINEABLE}
    strings |= set(mining_presenter._END_REASONS.values())
    strings |= set(combat_presenter._END_REASONS.values())
    strings |= set(combat_presenter.SITE_NAMES.values())
    strings |= set(trade_presenter._END_REASONS.values())
    strings |= set(engineering_presenter._GAINED.values())
    strings |= set(engineering_presenter._GAINED_ON_FOOT.values())
    strings |= set(engineering_names.SUIT_NAMES.values())
    strings |= set(engineering_presenter._END_REASONS.values())
    strings |= set(trade_presenter._TRANSFER_LABELS.values())
    # Names of the game data, shown in the player's language (ADR 0017)
    catalogue = load_catalogue()
    for entries in (
        catalogue.materials,
        catalogue.blueprints,
        catalogue.effects,
        catalogue.modules,
    ):
        strings |= {entry.english_name for entry in entries.values()}
    strings |= set(catalogue.engineers.values())
    strings |= set(catalogue.on_foot_engineers.values())
    return strings


def translations(language: str) -> dict[str, str]:
    lines = (ROOT / "L10n" / f"{language}.strings").read_text(encoding="utf-8").splitlines()
    return {match[1]: match[2] for line in lines if (match := TRANSLATION.match(line)) is not None}


def test_every_displayed_text_has_a_french_translation() -> None:
    missing = source_strings() - translations("fr").keys()
    assert not missing, f"missing in L10n/fr.strings: {sorted(missing)}"


def test_no_stale_translation() -> None:
    stale = translations("fr").keys() - source_strings()
    assert not stale, f"no longer used: {sorted(stale)}"


def test_placeholders_are_kept_in_translations() -> None:
    placeholder = re.compile(r"\{\w+\}")
    for source, translated in translations("fr").items():
        assert sorted(placeholder.findall(source)) == sorted(placeholder.findall(translated)), (
            source
        )
