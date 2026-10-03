import logging
from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.domain.commodities import Commodity
from edrockmaster.domain.prospecting import CoreAlert, ProspectorAlertRaised
from edrockmaster.infrastructure.clock import SystemClock
from edrockmaster.infrastructure.sound import SoundNotifier

logger = logging.getLogger("test.sound")
ALERT = ProspectorAlertRaised(
    at=datetime(2026, 10, 3, tzinfo=UTC), alerts=(CoreAlert(Commodity.from_symbol("painite")),)
)


def test_each_alert_plays_the_sound_once() -> None:
    played: list[None] = []
    SoundNotifier(lambda: played.append(None), logger).notify(ALERT)
    assert played == [None]


def test_a_failing_sound_is_logged_not_raised(caplog: pytest.LogCaptureFixture) -> None:
    def broken() -> None:
        raise RuntimeError("no audio device")

    with caplog.at_level(logging.WARNING):
        SoundNotifier(broken, logger).notify(ALERT)
    assert "no audio device" in caplog.text


def test_system_clock_is_utc_and_current() -> None:
    now = SystemClock().now()
    assert now.tzinfo is UTC
    assert abs(datetime.now(UTC) - now) < timedelta(seconds=5)
