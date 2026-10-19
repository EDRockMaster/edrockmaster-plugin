"""Updating the installed application (ADR 0053).

An installed application follows an update channel: ``stable`` (productions) or
``beta`` (candidates and productions), by default the one of the build, chosen
otherwise in the settings. A newer version of that channel is downloaded, then
applied when the application quits, or when the player restarts it to update;
the application never restarts by itself. A version lower than the one
installed is never installed: a local database may have been migrated beyond it.

``UpdateService`` decides; an ``UpdateSource`` (Velopack, in ``infrastructure``)
finds, downloads and applies. Its calls block on the network: the service runs on
a thread of its own, never on the core's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from edrockmaster.application.build import Channel

if TYPE_CHECKING:
    from edrockmaster.application.ports import UpdateSource


class UpdateChannel(Enum):
    STABLE = "stable"
    BETA = "beta"


_DEFAULT_CHANNELS = {
    Channel.PRODUCTION: UpdateChannel.STABLE,
    Channel.CANDIDATE: UpdateChannel.BETA,
    Channel.DEV: None,
}


def default_channel(channel: Channel) -> UpdateChannel | None:
    """The update channel of a build; ``None`` for a development build, never installed."""
    return _DEFAULT_CHANNELS[channel]


_SEMVER = re.compile(r"(?P<core>\d+\.\d+\.\d+)(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?")

type _Key = tuple[tuple[int, ...], tuple[tuple[int, int | str], ...]]


def _key(version: str) -> _Key | None:
    match = _SEMVER.fullmatch(version)
    if match is None:
        return None
    core = tuple(int(part) for part in match["core"].split("."))
    if match["pre"] is None:
        # A release ranks above its pre-releases: an empty identifier list compares lower
        # than any, so the release gets a marker above every identifier
        return core, ((2, 0),)
    return core, tuple(
        (0, int(part)) if part.isdigit() else (1, part) for part in match["pre"].split(".")
    )


def is_newer(version: str, than: str) -> bool:
    """SemVer precedence (build metadata ignored); ``False`` if either is not a version."""
    mine, theirs = _key(version), _key(than)
    return mine is not None and theirs is not None and mine > theirs


@dataclass(frozen=True, slots=True)
class UpdateReady:
    """A newer version is downloaded: applied when the application quits or restarts."""

    version: str


class UpdateService:
    """Called on the updates thread only."""

    def __init__(self, source: UpdateSource, default: UpdateChannel | None) -> None:
        self._source = source
        self._default = default
        self._ready: UpdateReady | None = None
        self._ready_channel: UpdateChannel | None = None
        self._applied = False

    @property
    def ready(self) -> UpdateReady | None:
        return self._ready

    def check(self, *, enabled: bool, chosen: UpdateChannel | None) -> UpdateReady | None:
        """Look for a newer version and download it; what became ready, if anything."""
        channel = chosen or self._default
        if not enabled or (self._ready is not None and channel is not self._ready_channel):
            self._ready = None  # not wanted anymore: never applied
        if not enabled:
            return None
        found = self._source.find(channel)
        if found is None or not is_newer(found, self._source.installed_version):
            return None
        if self._ready is not None and not is_newer(found, self._ready.version):
            return None
        self._source.download()
        self._ready, self._ready_channel = UpdateReady(found), channel
        return self._ready

    def restart(self) -> bool:
        """Apply the version ready once the application has quit, and start it again; ``False``
        if none is ready."""
        return self._apply(restart=True)

    def at_exit(self) -> None:
        """The application quits: the version ready, if any, is applied."""
        self._apply(restart=False)

    def _apply(self, *, restart: bool) -> bool:
        if self._ready is None or self._applied:
            return False
        self._source.apply(restart=restart)
        self._applied = True
        return True
