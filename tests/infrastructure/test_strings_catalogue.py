from pathlib import Path

import pytest

from edrockmaster.infrastructure.strings_catalogue import (
    number_format,
    read_strings,
    system_language,
    translator,
)


def test_french_comes_from_the_plugin_s_strings_file() -> None:
    tl = translator("fr")
    assert tl("No mining session") == "Aucune session de minage"
    assert tl("A text nobody translated") == "A text nobody translated"
    assert translator("en")("No mining session") == "No mining session"


def test_escaped_quotes_and_a_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "xx.strings"
    path.write_text('/* comment */\n"Say \\"hi\\"" = "Dis \\"salut\\"";\n', encoding="utf-8")
    assert read_strings(path) == {'Say "hi"': 'Dis "salut"'}
    assert read_strings(tmp_path / "missing.strings") == {}
    assert translator("xx", tmp_path)('Say "hi"') == 'Dis "salut"'


def test_numbers_as_each_language_writes_them() -> None:
    assert number_format("en")(1234567.891, 1) == "1,234,567.9"
    assert number_format("fr")(1234567.891, 1) == "1{0}234{0}567,9".format(chr(0x202F))


@pytest.mark.parametrize(
    ("environ", "language"),
    [
        ({"LANG": "fr_FR.UTF-8"}, "fr"),
        ({"LC_ALL": "en_GB.UTF-8", "LANG": "fr_FR.UTF-8"}, "en"),
        ({"LC_MESSAGES": "fr_CA.UTF-8"}, "fr"),
        ({"LANG": "de_DE.UTF-8"}, "en"),
        ({}, "en"),
    ],
)
def test_the_system_language_from_the_locale_variables(
    environ: dict[str, str], language: str
) -> None:
    assert system_language("linux", environ) == language


@pytest.mark.parametrize(
    ("language_id", "language"), [(0x040C, "fr"), (0x0C0C, "fr"), (0x0409, "en")]
)
def test_the_system_language_on_windows(language_id: int, language: str) -> None:
    assert system_language("win32", {}, lambda: language_id) == language
