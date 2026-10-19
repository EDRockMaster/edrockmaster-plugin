from types import ModuleType, SimpleNamespace
from typing import Any

import velopack

from edrockmaster.application.updates import UpdateChannel
from edrockmaster.infrastructure.velopack_updates import (
    REPOSITORY,
    SOURCE_VARIABLE,
    VelopackUpdates,
)


class FakeVelopack(ModuleType):
    """Velopack's classes as the adapter uses them; ``installed`` says whether the
    application is installed."""

    def __init__(self, installed: bool = True, latest: str | None = "0.7.1") -> None:
        super().__init__("velopack")
        self.installed = installed
        self.latest = latest
        self.managers: list[FakeManager] = []
        fake = self

        class GithubSource:
            def __init__(self, url: str, access_token: str | None = None, prerelease: bool = False):
                self.url, self.prerelease = url, prerelease

        class UpdateOptions:
            def __init__(self, **options: Any) -> None:
                self.options = options

        def update_manager(source: Any, options: UpdateOptions) -> FakeManager:
            if not fake.installed:
                raise RuntimeError("This application is not properly installed")
            manager = FakeManager(source, options.options, fake.latest)
            fake.managers.append(manager)
            return manager

        self.GithubSource = GithubSource
        self.UpdateOptions = UpdateOptions
        self.UpdateManager = update_manager


class FakeManager:
    def __init__(self, source: Any, options: dict[str, Any], latest: str | None) -> None:
        self.source, self.options, self.latest = source, options, latest
        self.calls: list[tuple[str, Any]] = []

    def get_current_version(self) -> str:
        return "0.7.0"

    def check_for_updates(self) -> Any:
        if self.latest is None:
            return None
        return SimpleNamespace(TargetFullRelease=SimpleNamespace(Version=self.latest))

    def download_updates(self, info: Any) -> None:
        self.calls.append(("download", info.TargetFullRelease.Version))

    def wait_exit_then_apply_updates(self, info: Any, silent: bool, restart: bool) -> None:
        self.calls.append(("apply", (info.TargetFullRelease.Version, silent, restart)))


def test_an_application_not_installed_has_no_updates() -> None:
    assert VelopackUpdates.installed({}, FakeVelopack(installed=False)) is None


def test_stable_reads_the_releases_and_beta_the_pre_releases_too() -> None:
    fake = FakeVelopack()
    updates = VelopackUpdates.installed({}, fake)
    assert updates is not None
    assert updates.installed_version == "0.7.0"
    assert updates.find(UpdateChannel.STABLE) == "0.7.1"
    stable = fake.managers[-1]
    assert (stable.source.url, stable.source.prerelease) == (REPOSITORY, False)
    assert stable.options == {
        "AllowVersionDowngrade": False,
        "MaximumDeltasBeforeFallback": 10,
        "ExplicitChannel": "stable",
    }
    updates.find(UpdateChannel.BETA)
    beta = fake.managers[-1]
    assert beta.source.prerelease
    assert beta.options["ExplicitChannel"] == "beta"


def test_the_version_found_is_downloaded_then_applied_once_the_application_quits() -> None:
    fake = FakeVelopack()
    updates = VelopackUpdates.installed({}, fake)
    assert updates is not None
    updates.find(UpdateChannel.STABLE)
    updates.download()
    updates.apply(restart=True)
    assert fake.managers[-1].calls == [("download", "0.7.1"), ("apply", ("0.7.1", True, True))]


def test_nothing_newer() -> None:
    updates = VelopackUpdates.installed({}, FakeVelopack(latest=None))
    assert updates is not None
    assert updates.find(UpdateChannel.STABLE) is None


def test_the_environment_names_another_source_and_the_installed_channel_is_followed() -> None:
    fake = FakeVelopack()
    updates = VelopackUpdates.installed({SOURCE_VARIABLE: "C:/feed"}, fake)
    assert updates is not None
    updates.find(None)
    assert fake.managers[-1].source == "C:/feed"
    assert fake.managers[-1].options["ExplicitChannel"] is None


def test_the_real_velopack_says_a_test_run_is_not_installed() -> None:
    assert VelopackUpdates.installed({}, velopack) is None
