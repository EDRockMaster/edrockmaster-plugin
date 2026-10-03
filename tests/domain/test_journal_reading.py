from datetime import UTC, datetime

import pytest

from edrockmaster.domain.journal_reading import (
    Entry,
    MalformedEntryError,
    Parser,
    localised,
    translate,
)

AT = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def event_name(entry: Entry, at: datetime) -> tuple[str, datetime]:
    return localised(entry, "Name"), at


PARSERS: dict[str, Parser[tuple[str, datetime]]] = {"Named": event_name}


def test_translate_dispatches_on_the_event_and_reads_the_timestamp() -> None:
    entry = {"timestamp": "2026-10-03T12:00:00Z", "event": "Named", "Name": "x"}
    assert translate(entry, PARSERS) == ("x", AT)


@pytest.mark.parametrize(
    "entry",
    [
        {"timestamp": "2026-10-03T12:00:00Z", "event": "Other"},
        {"timestamp": "yesterday", "event": "Named", "Name": "x"},
        {"timestamp": "2026-10-03T12:00:00Z", "event": "Named"},
        {"event": 3},
    ],
)
def test_irrelevant_or_malformed_entries_give_nothing(entry: Entry) -> None:
    assert translate(entry, PARSERS) is None


def test_localised_prefers_the_game_language() -> None:
    entry = {"Target": "empire_trader", "Target_Localised": "Imperial Clipper"}
    assert localised(entry, "Target") == "Imperial Clipper"
    assert localised({"Target": "empire_trader"}, "Target") == "empire_trader"


def test_localised_alone_is_enough() -> None:
    assert localised({"Target_Localised": "Imperial Clipper"}, "Target") == "Imperial Clipper"


def test_localised_requires_one_of_the_two_fields() -> None:
    with pytest.raises(MalformedEntryError):
        localised({}, "Target")
