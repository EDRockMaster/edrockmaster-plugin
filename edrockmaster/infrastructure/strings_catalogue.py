"""Translations of the desktop application's core texts, from ``L10n/<language>.strings``.

The plugin's presenters write English texts and translate them with ``tl()``;
in EDMC, ``tl`` reads ``L10n/fr.strings``. The desktop application reads the
same files (ADR 0020), until its views move to the interface's catalogues
(ADR 0021). Numbers are written as the language writes them.
"""

from __future__ import annotations

import locale
import re
from collections.abc import Callable
from pathlib import Path

L10N_DIRECTORY = Path(__file__).resolve().parents[2] / "L10n"
LANGUAGES = ("en", "fr")
_LINE = re.compile(r'^\s*"((?:[^"\\]|\\.)+)"\s*=\s*"((?:[^"\\]|\\.)+)"\s*;\s*$')
_NARROW_NO_BREAK_SPACE = chr(0x202F)  # as French typography separates thousands


def read_strings(path: Path) -> dict[str, str]:
    """English source text → translation; an absent file is no translation."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {}
    return {
        _unescape(match[1]): _unescape(match[2])
        for line in lines
        if (match := _LINE.match(line)) is not None
    }


def _unescape(text: str) -> str:
    return text.replace('\\"', '"').replace("\\\\", "\\")


def translator(language: str, directory: Path = L10N_DIRECTORY) -> Callable[[str], str]:
    """``tl()`` for a language: the translation, else the English text."""
    if language == "en":
        return lambda text: text
    translations = read_strings(directory / f"{language}.strings")
    return lambda text: translations.get(text, text)


def number_format(language: str) -> Callable[[float, int], str]:
    """Numbers as the language writes them: ``1,234.5`` in English, ``1 234,5`` in French."""
    if language == "fr":

        def french(number: float, decimals: int) -> str:
            text = f"{number:,.{decimals}f}"
            return text.replace(",", _NARROW_NO_BREAK_SPACE).replace(".", ",")

        return french
    return lambda number, decimals: f"{number:,.{decimals}f}"


def system_language(get_locale: Callable[[], str | None] | None = None) -> str:
    """The system's language if the application has it, else English."""
    name = (get_locale or (lambda: locale.getlocale()[0]))() or ""
    lowered = name.lower()
    # "fr_FR" on Linux; "French_France" on Windows
    if lowered.startswith(("fr", "french")):
        return "fr"
    return "en"
