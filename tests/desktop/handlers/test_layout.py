"""The cards' layout calls, on a core context that runs each job at once (ADR 0041)."""

import logging

import pytest

from edrockmaster.desktop.handlers.layout import LayoutHandler
from edrockmaster.desktop.layout import LayoutStore
from tests.desktop.handlers.fake_core import FakeCore
from tests.fakes import FakeConfig

ENGINEERING = {"order": ["inventory"], "folded": ["engineers"]}


def test_the_layout_saved_is_kept(caplog: pytest.LogCaptureFixture) -> None:
    config = FakeConfig()
    handler = LayoutHandler(FakeCore().context, LayoutStore(config))
    assert handler.layout()["engineering"]["order"][0] == "goals"
    with caplog.at_level(logging.WARNING):
        handler.save_layout("blueprints", {"order": [], "folded": []})
        handler.save_layout("engineering", ENGINEERING)
    assert "Layout refused: unknown view 'blueprints'" in caplog.text
    assert handler.layout()["engineering"] == {
        "order": ["inventory", "goals", "shopping", "engineers"],
        "folded": ["engineers"],
    }
    again = LayoutHandler(FakeCore().context, LayoutStore(config))
    assert again.layout()["engineering"]["folded"] == ["engineers"]


def test_an_unchanged_layout_is_not_written_again() -> None:
    config = FakeConfig()
    handler = LayoutHandler(FakeCore().context, LayoutStore(config))
    handler.save_layout("engineering", ENGINEERING)
    written = dict(config.values)
    config.values.clear()
    handler.save_layout("engineering", ENGINEERING)
    assert config.values == {}
    assert written
