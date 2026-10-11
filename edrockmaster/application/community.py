"""What the community sources answer (ADR 0039).

A source is asked only on the player's action, and may be off, busy or down.
Its answer is either what it found, read now or from the local cache, or why
nothing could be had. A value from the cache when the source failed says why.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Source(Enum):
    SPANSH = "spansh"
    ARDENT = "ardent"


class Unavailable(Enum):
    """Why a source gave nothing new."""

    OFF = "off"
    """The player turned it off."""
    BUSY = "busy"
    """It asked us to wait (too many requests, or overloaded)."""
    DOWN = "down"
    """Unreachable, or its answer could not be read."""


@dataclass(frozen=True, slots=True)
class Found[T]:
    value: T
    source: Source
    read_at: datetime
    """When the source was read: now, or when the cached answer was."""
    unavailable: Unavailable | None = None
    """Set when the source failed and the cache answered instead."""


@dataclass(frozen=True, slots=True)
class Failed:
    source: Source
    reason: Unavailable


type Answer[T] = Found[T] | Failed
