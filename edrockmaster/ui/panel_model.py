"""What an activity block displays, as texts, and the formatting shared by the presenters.

Presenters are pure Python, no interface toolkit: the live view only copies the
texts of a ``PanelModel``. They keep domain objects, not texts, so that ``render()``
rebuilds everything in the current language after the player changes it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from edrockmaster.application.activity import Activity

type Translate = Callable[[str], str]

type NumberFormat = Callable[[float, int], str]
"""Formats a number with the given count of decimals."""


def default_number_format(number: float, decimals: int) -> str:
    return f"{number:,.{decimals}f}"


def identity(text: str) -> str:
    return text


@dataclass(frozen=True, slots=True)
class StatLine:
    label: str
    value: str
    until: datetime | None = None
    """A moment the interface counts down to, after the value (a community goal's expiry)."""


@dataclass(frozen=True, slots=True)
class PanelModel:
    status: str
    lines: tuple[StatLine, ...]
    alert: str | None
    can_reset: bool


@dataclass(frozen=True, slots=True)
class ActivityBlock:
    """One activity's part of the panel: one block, or one per activity when stacked."""

    activity: Activity
    model: PanelModel


class LocalDataNotice(Enum):
    """Why the interface warns about the local data (ADR 0018)."""

    RESET = "reset"
    """The database could not be read: it was moved aside and a new one created."""
    UNAVAILABLE = "unavailable"
    """The database could not be opened: nothing is stored until the application restarts."""


def format_duration(duration: timedelta, translate: Translate) -> str:
    minutes = int(duration.total_seconds() // 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return translate("{hours} h {minutes} min").format(hours=hours, minutes=f"{minutes:02d}")
    return translate("{minutes} min").format(minutes=minutes)


MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def format_day(moment: datetime, translate: Translate) -> str:
    """A day in words, ``14 October 2026``: no order of day and month to guess."""
    return translate("{day} {month} {year}").format(
        day=moment.day, month=translate(MONTHS[moment.month - 1]), year=moment.year
    )


def format_credits(credits: float, translate: Translate, format_number: NumberFormat) -> str:
    return translate("{credits} CR").format(credits=format_number(credits, 0))
