"""What the panel displays, as texts, and the formatting shared by the presenters.

Presenters are pure Python, no tkinter: the panel only copies the texts of a
``PanelModel``. They keep domain objects, not texts, so that ``render()``
rebuilds everything in the current language after the player changes it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import assert_never

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
    """Why the panel warns about the plugin's local data (ADR 0018)."""

    RESET = "reset"
    """The database could not be read: it was moved aside and a new one created."""
    UNAVAILABLE = "unavailable"
    """The database could not be opened: nothing is stored until EDMC restarts."""


def notice_text(notice: LocalDataNotice, translate: Translate) -> str:
    match notice:
        case LocalDataNotice.RESET:
            return translate("Local data could not be read and was reset, see the EDMC log")
        case LocalDataNotice.UNAVAILABLE:
            return translate("Local data is unavailable until EDMC restarts, see the EDMC log")
        case _:  # pragma: no cover - exhaustiveness checked by mypy
            assert_never(notice)


def format_duration(duration: timedelta, translate: Translate) -> str:
    minutes = int(duration.total_seconds() // 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return translate("{hours} h {minutes} min").format(hours=hours, minutes=f"{minutes:02d}")
    return translate("{minutes} min").format(minutes=minutes)


def format_credits(credits: float, translate: Translate, format_number: NumberFormat) -> str:
    return translate("{credits} CR").format(credits=format_number(credits, 0))
