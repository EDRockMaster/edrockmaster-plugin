"""The route's alerts sound like the others, only when they happen now (ADR 0043)."""

from datetime import UTC, datetime, timedelta

from edrockmaster.application.situation_service import SituationService
from edrockmaster.domain.journal_reading import Entry
from edrockmaster.domain.situation.route import RouteAlert, RouteAlertRaised
from tests.fakes import FakeNotifier, FixedClock

AT = datetime(2026, 10, 12, 11, 0, tzinfo=UTC)
DWARF = [
    {"StarSystem": "Sol", "StarClass": "G"},
    {"StarSystem": "Sirius B", "StarClass": "DA"},
    {"StarSystem": "Procyon", "StarClass": "F"},
]


def plot(service: SituationService, at: datetime) -> list[object]:
    entry: Entry = {"timestamp": at.strftime("%Y-%m-%dT%H:%M:%SZ"), "event": "NavRoute"}
    return list(service.handle_journal_entry({**entry, "Route": DWARF}))


def test_an_alert_happening_now_sounds() -> None:
    notifier = FakeNotifier()
    service = SituationService(notifier, FixedClock(AT + timedelta(seconds=30)), lambda: True)
    notifications = plot(service, AT)
    raised = RouteAlertRaised(AT, RouteAlert.DANGEROUS_STAR, "Sirius B")
    assert raised in notifications
    assert notifier.notified == [raised]


def test_an_alert_read_again_at_start_is_silent() -> None:
    notifier = FakeNotifier()
    service = SituationService(notifier, FixedClock(AT + timedelta(hours=2)), lambda: True)
    assert any(isinstance(n, RouteAlertRaised) for n in plot(service, AT))
    assert notifier.notified == []


def test_no_sound_when_sound_is_off() -> None:
    notifier = FakeNotifier()
    service = SituationService(notifier, FixedClock(AT), lambda: False)
    plot(service, AT)
    assert notifier.notified == []


def test_an_entry_the_situation_ignores() -> None:
    service = SituationService(FakeNotifier(), FixedClock(AT), lambda: True)
    assert (
        service.handle_journal_entry({"timestamp": "2026-10-12T11:00:00Z", "event": "Music"}) == []
    )
