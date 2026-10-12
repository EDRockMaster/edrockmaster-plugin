"""The Mining tab's calls when the sources are slow or the work fails (ADR 0040, ADR 0041).

The searches themselves, through the core, are in ``tests/desktop/test_mining_tab.py``.
"""

from collections.abc import Callable
from typing import Any

import pytest

from edrockmaster.desktop.handlers import mining as mining_module
from edrockmaster.desktop.handlers.mining import MiningHandler
from tests.desktop.handlers.fake_core import FakeCore

BUYERS = {"commodity": "painite", "system": "Borann", "maxDistance": 50, "pad": "large"}


class SilentSearch:
    """Never answers, or fails at once."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error

    def find_buyers(self, query: object, answer: Callable[[Any], None], refresh: bool) -> None:
        if self._error is not None:
            raise self._error


def test_a_search_that_takes_too_long_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mining_module, "SEARCH_TIMEOUT", 0.05)
    handler = MiningHandler(FakeCore().context, SilentSearch())  # type: ignore[arg-type]
    answer = handler.find_buyers({**BUYERS, "carriers": False})
    assert (answer["status"], answer["offers"]) == ("down", [])


def test_a_search_that_fails_fails_the_call() -> None:
    search = SilentSearch(RuntimeError("broken"))
    handler = MiningHandler(FakeCore().context, search)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="broken"):
        handler.find_buyers({**BUYERS, "carriers": False})
