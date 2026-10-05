"""Decide where a release tag is published, and refuse what must not be (ADR 0012).

- ``vX.Y.Z-rc.N``: a release candidate, published as a private pre-release on Gitea
  for acceptance in game.
- ``vX.Y.Z``: production (GitHub and Gitea), allowed only on a commit that also
  carries an accepted candidate ``vX.Y.Z-rc.N``: players get what was accepted.

The tag must match the version of the code (``pyproject.toml``, ``VERSION``).

Usage: python3 scripts/release_plan.py <tag> <version> <tags on the commit>...
Prints ``channel=…`` and ``prerelease=…`` lines, for ``$GITHUB_OUTPUT``.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass

_TAG = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)(?:-rc\.(?P<candidate>[1-9]\d*))?$")


class ReleaseError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Plan:
    channel: str
    version: str
    candidate: int | None


def plan(tag: str, version: str, tags_on_commit: Iterable[str]) -> Plan:
    match = _TAG.match(tag)
    if match is None:
        raise ReleaseError(f"tag {tag!r} is neither vX.Y.Z nor vX.Y.Z-rc.N")
    if match["version"] != version:
        raise ReleaseError(f"tag {tag} does not match the version of the code, {version}")
    if match["candidate"] is not None:
        return Plan(channel="candidate", version=version, candidate=int(match["candidate"]))
    candidates = [
        other
        for other in tags_on_commit
        if (found := _TAG.match(other)) and found["version"] == version and found["candidate"]
    ]
    if not candidates:
        raise ReleaseError(
            f"no release candidate v{version}-rc.N on this commit: "
            "tag a candidate, accept it in game, then tag the release on the same commit"
        )
    return Plan(channel="production", version=version, candidate=None)


def main(arguments: list[str]) -> int:
    if len(arguments) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    tag, version, *tags_on_commit = arguments
    try:
        decided = plan(tag, version, tags_on_commit)
    except ReleaseError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    print(f"channel={decided.channel}")
    print(f"prerelease={'true' if decided.channel == 'candidate' else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
