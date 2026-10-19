import pytest

from edrockmaster.application.build import Channel
from edrockmaster.application.updates import (
    UpdateChannel,
    UpdateReady,
    UpdateService,
    default_channel,
    is_newer,
)


class FakeSource:
    def __init__(self, installed: str = "0.7.0") -> None:
        self.installed_version = installed
        self.latest: dict[UpdateChannel | None, str] = {}
        self.asked: list[UpdateChannel | None] = []
        self.downloaded: list[str] = []
        self.applied: list[bool] = []
        self._found: str | None = None

    def find(self, channel: UpdateChannel | None) -> str | None:
        self.asked.append(channel)
        self._found = self.latest.get(channel)
        return self._found

    def download(self) -> None:
        assert self._found is not None
        self.downloaded.append(self._found)

    def apply(self, *, restart: bool) -> None:
        self.applied.append(restart)


@pytest.mark.parametrize(
    ("channel", "expected"),
    [
        (Channel.PRODUCTION, UpdateChannel.STABLE),
        (Channel.CANDIDATE, UpdateChannel.BETA),
        (Channel.DEV, None),
    ],
)
def test_a_build_follows_the_channel_it_was_published_on(
    channel: Channel, expected: UpdateChannel | None
) -> None:
    assert default_channel(channel) is expected


@pytest.mark.parametrize(
    ("version", "than", "newer"),
    [
        ("0.7.1", "0.7.0", True),
        ("0.7.0", "0.7.0", False),
        ("0.7.0", "0.7.0-rc.3", True),
        ("0.7.0-rc.3", "0.7.0", False),
        ("0.7.0-rc.10", "0.7.0-rc.9", True),
        ("0.8.0-rc.1", "0.7.5", True),
        ("0.10.0", "0.9.0", True),
        ("1.0.1", "1.0.0", True),
        ("not a version", "0.7.0", False),
        ("0.7.1", "0.7.0-dev+2606b47", True),
    ],
)
def test_versions_compare_as_semver(version: str, than: str, newer: bool) -> None:
    assert is_newer(version, than) is newer


def test_off_checks_nothing() -> None:
    source = FakeSource()
    source.latest[UpdateChannel.STABLE] = "0.7.1"
    service = UpdateService(source, UpdateChannel.STABLE)
    assert service.check(enabled=False, chosen=None) is None
    assert source.asked == []


def test_a_newer_version_of_the_channel_is_downloaded_and_ready() -> None:
    source = FakeSource()
    source.latest[UpdateChannel.STABLE] = "0.7.1"
    service = UpdateService(source, UpdateChannel.STABLE)
    assert service.check(enabled=True, chosen=None) == UpdateReady("0.7.1")
    assert source.downloaded == ["0.7.1"]
    assert service.ready == UpdateReady("0.7.1")


def test_nothing_newer_is_nothing_to_do() -> None:
    service = UpdateService(FakeSource(), UpdateChannel.STABLE)
    assert service.check(enabled=True, chosen=None) is None
    assert service.ready is None


def test_the_channel_chosen_wins_over_the_build_s() -> None:
    source = FakeSource()
    source.latest[UpdateChannel.BETA] = "0.8.0-rc.1"
    service = UpdateService(source, UpdateChannel.STABLE)
    assert service.check(enabled=True, chosen=UpdateChannel.BETA) == UpdateReady("0.8.0-rc.1")
    assert source.asked == [UpdateChannel.BETA]


def test_a_lower_version_is_never_installed() -> None:
    # Back to stable from a candidate: wait for a production above it (ADR 0053)
    source = FakeSource(installed="0.8.0-rc.2")
    source.latest[UpdateChannel.STABLE] = "0.7.1"
    service = UpdateService(source, UpdateChannel.BETA)
    assert service.check(enabled=True, chosen=UpdateChannel.STABLE) is None
    assert source.downloaded == []


def test_a_version_ready_is_not_downloaded_again() -> None:
    source = FakeSource()
    source.latest[UpdateChannel.STABLE] = "0.7.1"
    service = UpdateService(source, UpdateChannel.STABLE)
    service.check(enabled=True, chosen=None)
    assert service.check(enabled=True, chosen=None) is None
    assert source.downloaded == ["0.7.1"]
    source.latest[UpdateChannel.STABLE] = "0.7.2"
    assert service.check(enabled=True, chosen=None) == UpdateReady("0.7.2")


def test_another_channel_forgets_the_version_ready() -> None:
    source = FakeSource()
    source.latest[UpdateChannel.BETA] = "0.8.0-rc.1"
    service = UpdateService(source, UpdateChannel.BETA)
    service.check(enabled=True, chosen=None)
    assert service.check(enabled=True, chosen=UpdateChannel.STABLE) is None
    assert service.ready is None
    service.at_exit()
    assert source.applied == []


def test_turned_off_forgets_the_version_ready() -> None:
    source = FakeSource()
    source.latest[UpdateChannel.STABLE] = "0.7.1"
    service = UpdateService(source, UpdateChannel.STABLE)
    service.check(enabled=True, chosen=None)
    service.check(enabled=False, chosen=None)
    assert service.ready is None


def test_a_version_ready_is_applied_at_exit_or_on_restart() -> None:
    source = FakeSource()
    service = UpdateService(source, UpdateChannel.STABLE)
    service.at_exit()
    assert not service.restart()
    assert source.applied == []
    source.latest[UpdateChannel.STABLE] = "0.7.1"
    service.check(enabled=True, chosen=None)
    assert service.restart()
    service.at_exit()
    assert source.applied == [True]  # once: the restart already applies it


def test_without_a_channel_the_installed_one_is_followed() -> None:
    # A build installed for the update test: its packed channel decides
    source = FakeSource()
    source.latest[None] = "1.0.1"
    service = UpdateService(source, None)
    assert service.check(enabled=True, chosen=None) == UpdateReady("1.0.1")
    assert source.asked == [None]
