"""Shared kernel: tolerant reading of raw journal entries (ADR 0011).

Each activity translates the journal into its own facts with these helpers;
this module holds no activity rule. A malformed entry raises
``MalformedEntryError`` inside a parser, and ``translate`` turns it into
``None``: unknown events, unknown fields and malformed entries are ignored,
never fatal.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from edrockmaster.domain.commodities import Commodity

type Entry = Mapping[str, object]

type Parser[F] = Callable[[Entry, datetime], F]
"""Reads one kind of event; may return ``None`` when the entry is irrelevant after all."""


class MalformedEntryError(Exception):
    """An entry lacks a required field, or a field has a wrong type."""


def translate[F](entry: Entry, parsers: Mapping[str, Parser[F]]) -> F | None:
    """Return the fact a parser reads from the entry, or ``None`` if irrelevant or malformed."""
    event = entry.get("event")
    parser = parsers.get(event) if isinstance(event, str) else None
    if parser is None:
        return None
    try:
        return parser(entry, timestamp(entry))
    except MalformedEntryError:
        return None


def timestamp(entry: Entry) -> datetime:
    raw = required(entry, "timestamp", str)
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise MalformedEntryError from error


def required[T](entry: Entry, name: str, kind: type[T]) -> T:
    value = entry.get(name)
    if not isinstance(value, kind) or (isinstance(value, bool) and kind is not bool):
        raise MalformedEntryError(name)
    return value


def optional[T](entry: Entry, name: str, kind: type[T]) -> T | None:
    return required(entry, name, kind) if name in entry else None


def number(entry: Entry, name: str) -> float | None:
    value = entry.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MalformedEntryError(name)
    return float(value)


def localised(entry: Entry, name: str) -> str:
    """A text field in the game's language when the journal gives it, else as is."""
    return optional(entry, f"{name}_Localised", str) or required(entry, name, str)


def commodity(entry: Entry, name: str) -> Commodity:
    try:
        return Commodity.from_symbol(
            required(entry, name, str), optional(entry, f"{name}_Localised", str)
        )
    except ValueError as error:
        raise MalformedEntryError(name) from error


def items(entry: Entry, name: str) -> list[Entry]:
    found = required(entry, name, list)
    if not all(isinstance(item, Mapping) for item in found):
        raise MalformedEntryError(name)
    return found
