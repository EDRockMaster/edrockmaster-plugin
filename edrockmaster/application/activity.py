"""The activities the application assists, each one a bounded context (ADR 0011)."""

from __future__ import annotations

from enum import Enum


class Activity(Enum):
    MINING = "mining"
    COMBAT = "combat"
    TRADE = "trade"
    ENGINEERING = "engineering"
