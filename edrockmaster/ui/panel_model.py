"""What the panel displays, as texts, and the formatting shared by the presenters.

Presenters are pure Python, no tkinter: the panel only copies the texts of a
``PanelModel``. They keep domain objects, not texts, so that ``render()``
rebuilds everything in the current language after the player changes it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

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


@dataclass(frozen=True, slots=True)
class PanelModel:
    status: str
    lines: tuple[StatLine, ...]
    alert: str | None
    can_reset: bool


def format_duration(duration: timedelta, translate: Translate) -> str:
    minutes = int(duration.total_seconds() // 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return translate("{hours} h {minutes} min").format(hours=hours, minutes=f"{minutes:02d}")
    return translate("{minutes} min").format(minutes=minutes)


def format_credits(credits: float, translate: Translate, format_number: NumberFormat) -> str:
    return translate("{credits} CR").format(credits=format_number(credits, 0))
