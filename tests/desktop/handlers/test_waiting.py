"""A search's call when the sources are slow or the work fails (ADR 0039, ADR 0041).

The searches themselves, through the core, are in ``tests/desktop/test_mining_tab.py`` and
``tests/desktop/test_trade_tab.py``.
"""

from collections.abc import Callable
from typing import Any

import pytest

from edrockmaster.desktop.handlers import waiting
from edrockmaster.desktop.handlers.trade import TradeHandler
from edrockmaster.infrastructure.commodity_catalogue_file import load_commodities
from tests.desktop.handlers.fake_core import FakeCore

BUYERS = {
    "side": "sell",
    "commodity": "painite",
    "system": "Borann",
    "maxDistance": 50,
    "pad": "large",
    "carriers": False,
    "minVolume": 1,
}


class SilentSearch:
    """Never answers, or fails at once."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error

    def find_offers(self, query: object, answer: Callable[[Any], None], refresh: bool) -> None:
        if self._error is not None:
            raise self._error


def test_a_search_that_takes_too_long_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(waiting, "SEARCH_TIMEOUT", 0.05)
    handler = TradeHandler(
        FakeCore().context,
        load_commodities(),
        SilentSearch(),  # type: ignore[arg-type]
        SilentSearch(),  # type: ignore[arg-type]
    )
    answer = handler.find_markets(BUYERS)
    assert (answer["status"], answer["offers"]) == ("down", [])


def test_a_search_that_fails_fails_the_call() -> None:
    search = SilentSearch(RuntimeError("broken"))
    handler = TradeHandler(
        FakeCore().context,
        load_commodities(),
        search,  # type: ignore[arg-type]
        search,  # type: ignore[arg-type]
    )
    with pytest.raises(RuntimeError, match="broken"):
        handler.find_markets(BUYERS)
