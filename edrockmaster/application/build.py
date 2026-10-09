"""Which build of the application is running (ADR 0016).

The code carries the base version ``X.Y.Z`` only, the same for a candidate and for
production (ADR 0012). The packaging writes ``edrockmaster/build.json`` into the zip,
with the full version, the commit and the channel; a clone has none and is a
development build.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum

BUILD_FILE_NAME = "build.json"

_COMMIT = re.compile(r"[0-9a-f]{40}")
_SHORT_COMMIT = 7


class Channel(Enum):
    """Where a build was published (ADR 0012)."""

    PRODUCTION = "production"
    CANDIDATE = "candidate"
    DEV = "dev"


def _version_pattern(channel: Channel, base_version: str) -> re.Pattern[str]:
    base = re.escape(base_version)
    return re.compile(
        {
            Channel.PRODUCTION: base,
            Channel.CANDIDATE: rf"{base}-rc\.[1-9]\d*",
            Channel.DEV: rf"{base}-dev(?:\+[0-9a-f]+)?",
        }[channel]
    )


class BuildFileError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BuildInfo:
    version: str
    """Full SemVer version: ``0.3.0``, ``0.3.0-rc.2``, ``0.3.0-dev+2606b47``, ``0.3.0-dev``."""
    channel: Channel
    commit: str | None = None
    """Full hash of the commit built; unknown for a clone."""

    @property
    def short_commit(self) -> str | None:
        return self.commit[:_SHORT_COMMIT] if self.commit is not None else None


def development_build(base_version: str) -> BuildInfo:
    """The identity of an application run from a clone, or whose build file is unusable."""
    return BuildInfo(version=f"{base_version}-dev", channel=Channel.DEV)


def parse_build_file(text: str, base_version: str) -> BuildInfo:
    """Read a build file; it must match the base version of the code."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise BuildFileError(f"not JSON: {error}") from error
    if not isinstance(data, dict):
        raise BuildFileError("not a JSON object")
    version, channel_name, commit = data.get("version"), data.get("channel"), data.get("commit")
    try:
        channel = Channel(channel_name)
    except ValueError:
        raise BuildFileError(f"unknown channel {channel_name!r}") from None
    if not isinstance(version, str) or not _version_pattern(channel, base_version).fullmatch(
        version
    ):
        raise BuildFileError(
            f"version {version!r} is not a {channel.value} build of {base_version}"
        )
    if commit is not None and not (isinstance(commit, str) and _COMMIT.fullmatch(commit)):
        raise BuildFileError(f"commit {commit!r} is not a full commit hash")
    return BuildInfo(version=version, channel=channel, commit=commit)


def build_file_content(version: str, channel: str, commit: str, base_version: str) -> str:
    """The build file the packaging writes; refused if the application would not accept it."""
    text = json.dumps({"version": version, "commit": commit, "channel": channel})
    parse_build_file(text, base_version)
    return text + "\n"
