"""Translations of the desktop application's core texts, from ``L10n/<language>.strings``.

The presenters write English texts and translate them with ``tl()``, which
reads ``L10n/<language>.strings``; the interface has its own catalogues
(ADR 0021). Numbers are written as the language writes them.
"""

from __future__ import annotations

import ctypes
import os
import re
import sys
from collections.abc import Callable, Mapping
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


def system_language(
    platform: str = sys.platform,
    environ: Mapping[str, str] = os.environ,
    windows_ui_language: Callable[[], int] | None = None,
) -> str:
    """The language of the system's interface if the application has it, else English.

    On Windows, the language of the user interface; elsewhere, the locale variables.
    """
    if platform == "win32":
        language_id = (windows_ui_language or _windows_ui_language)()
        # The primary language is the low 10 bits of a Windows language id
        return "fr" if language_id & 0x3FF == _WINDOWS_FRENCH else "en"
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = environ.get(name, "")
        if value:
            return "fr" if value.lower().startswith("fr") else "en"
    return "en"


_WINDOWS_FRENCH = 0x0C


def _windows_ui_language() -> int:  # pragma: no cover - Windows only
    return int(ctypes.windll.kernel32.GetUserDefaultUILanguage())  # type: ignore[attr-defined]
