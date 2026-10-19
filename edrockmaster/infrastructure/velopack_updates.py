"""The installed application's updates, through Velopack (ADR 0053).

The releases of the public GitHub repository are the source: productions on the
``stable`` channel, candidates as pre-releases on the ``beta`` channel only.
``EDROCKMASTER_UPDATE_SOURCE`` names another source, a folder or an address: the
update test of the Windows build serves a local feed with it.

An application not installed by Velopack (a clone, a CI build) has nothing to
update: ``VelopackUpdates.installed`` gives ``None``. Every call blocks on the network
or the disk.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import ModuleType
from typing import Any

import velopack

from edrockmaster.application.updates import UpdateChannel

REPOSITORY = "https://github.com/EDRockMaster/edrockmaster-plugin"
SOURCE_VARIABLE = "EDROCKMASTER_UPDATE_SOURCE"
DELTAS_BEFORE_FULL = 10
"""Velopack's default: beyond that many deltas, the full package is downloaded."""


class VelopackUpdates:
    def __init__(self, override: str | None = None, module: ModuleType = velopack) -> None:
        """``override``: the source to use instead of the GitHub releases."""
        self._override = override
        self._velopack = module
        self._manager: Any = self._new_manager(None)
        self._found: Any = None

    @classmethod
    def installed(
        cls, environ: Mapping[str, str], module: ModuleType = velopack
    ) -> VelopackUpdates | None:
        """The updates of this installation; ``None`` if Velopack did not install it."""
        try:
            return cls(environ.get(SOURCE_VARIABLE) or None, module)
        except RuntimeError:  # "This application is not properly installed"
            return None

    @property
    def installed_version(self) -> str:
        return str(self._manager.get_current_version())

    def find(self, channel: UpdateChannel | None) -> str | None:
        self._manager = self._new_manager(channel)
        self._found = self._manager.check_for_updates()
        return str(self._found.TargetFullRelease.Version) if self._found else None

    def download(self) -> None:
        self._manager.download_updates(self._found)

    def apply(self, *, restart: bool) -> None:
        # Update.exe waits for the application to quit, then applies, without a window
        self._manager.wait_exit_then_apply_updates(self._found, silent=True, restart=restart)

    def _new_manager(self, channel: UpdateChannel | None) -> Any:
        source: Any = self._override or self._velopack.GithubSource(
            REPOSITORY, prerelease=channel is UpdateChannel.BETA
        )
        options = self._velopack.UpdateOptions(
            # Never a downgrade: a lower version may meet a database migrated beyond it
            AllowVersionDowngrade=False,
            MaximumDeltasBeforeFallback=DELTAS_BEFORE_FULL,
            ExplicitChannel=channel.value if channel else None,
        )
        return self._velopack.UpdateManager(source, options)
