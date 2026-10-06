"""The activities the plugin assists, each one a bounded context (ADR 0011)."""

from __future__ import annotations

from enum import Enum


class Activity(Enum):
    MINING = "mining"
    COMBAT = "combat"
    TRADE = "trade"
