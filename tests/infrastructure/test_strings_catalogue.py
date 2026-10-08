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
    ("name", "language"),
    [("fr_FR", "fr"), ("French_France", "fr"), ("en_GB", "en"), ("de_DE", "en"), (None, "en")],
)
def test_the_system_language(name: str | None, language: str) -> None:
    assert system_language(lambda: name) == language


def test_the_system_language_by_default() -> None:
    assert system_language() in ("en", "fr")
