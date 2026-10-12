"""The limpet alert (ADR 0042): once when the limpets on board fall to the threshold."""

from datetime import UTC, datetime, timedelta

import pytest

from edrockmaster.domain.mining.limpets import LimpetAlertRaised, LimpetMonitor

T0 = datetime(2026, 10, 12, 20, 0, tzinfo=UTC)


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def test_alerts_once_when_the_count_falls_to_the_threshold() -> None:
    monitor = LimpetMonitor(5)
    assert monitor.evaluate(8, at(0)) is None
    assert monitor.evaluate(6, at(1)) is None
    assert monitor.evaluate(5, at(2)) == LimpetAlertRaised(at(2), 5)
    # Not at every launch below it
    assert monitor.evaluate(4, at(3)) is None
    assert monitor.evaluate(0, at(4)) is None


def test_is_re_armed_once_the_count_rises_above_the_threshold() -> None:
    monitor = LimpetMonitor(5)
    assert monitor.evaluate(3, at(0)) == LimpetAlertRaised(at(0), 3)
    # Still at or below: not re-armed
    assert monitor.evaluate(5, at(1)) is None
    assert monitor.evaluate(20, at(2)) is None
    assert monitor.evaluate(4, at(3)) == LimpetAlertRaised(at(3), 4)


def test_a_count_already_low_alerts_once() -> None:
    monitor = LimpetMonitor(5)
    assert monitor.evaluate(2, at(0)) == LimpetAlertRaised(at(0), 2)
    assert monitor.evaluate(2, at(1)) is None


def test_no_threshold_no_alert() -> None:
    monitor = LimpetMonitor(None)
    assert monitor.evaluate(0, at(0)) is None


def test_a_new_threshold_re_arms_it() -> None:
    monitor = LimpetMonitor(5)
    assert monitor.evaluate(4, at(0)) is not None
    # The same threshold saved again does not alert twice
    monitor.update_threshold(5)
    assert monitor.evaluate(4, at(1)) is None
    monitor.update_threshold(3)
    assert monitor.evaluate(4, at(1)) is None
    assert monitor.evaluate(3, at(2)) == LimpetAlertRaised(at(2), 3)


def test_rearm_lets_the_next_session_alert() -> None:
    monitor = LimpetMonitor(5)
    assert monitor.evaluate(4, at(0)) is not None
    monitor.rearm()
    assert monitor.evaluate(4, at(1)) == LimpetAlertRaised(at(1), 4)


def test_a_negative_threshold_is_refused() -> None:
    with pytest.raises(ValueError, match="limpet"):
        LimpetMonitor(-1)
