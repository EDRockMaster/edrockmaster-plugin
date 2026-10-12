"""Wait for the Windows build of a commit on the GitHub mirror, and take its result (ADR 0034).

The Windows workflow (``.github/workflows/windows.yml``) runs on the public GitHub mirror only;
the Gitea CI runs this script so that a failed Windows build blocks merging there too.

- The commit's own run is waited for, then taken: success passes, anything else fails.
- A commit that changed only what the Windows workflow ignores (its ``paths-ignore``) gets no
  run: the run of its nearest ancestor that has one counts, when everything changed since is
  ignored as well. A branch that changed only such files needs no build at all.
- On a tag, the tag's own run is preferred; otherwise the latest run of the commit (a rerun).
- No result after ``--timeout`` seconds (20 minutes by default) is a failure. GitHub not
  answering (a 502, the network) is asked again until then: it says nothing of the build.

The GitHub API is read with ``GH_ACTIONS_READ_TOKEN`` when set (a read-only token, only for
the rate limit), anonymously otherwise: the mirror is public.

Usage: python3 scripts/windows_build_gate.py <commit> [--ref <tag>] [--base <branch>]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

MIRROR = "EDRockMaster/edrockmaster-plugin"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "windows.yml"
ANCESTORS = 50
"""How far back to look for a commit that has a run."""
POLL_SECONDS = 20


@dataclass(frozen=True, slots=True)
class Run:
    sha: str
    status: str
    conclusion: str | None
    url: str
    branch: str
    created: float


@dataclass(frozen=True, slots=True)
class Wait:
    """No result yet: the run to wait for, or ``None`` while it has not started."""

    run: Run | None


@dataclass(frozen=True, slots=True)
class Result:
    run: Run

    @property
    def passed(self) -> bool:
        return self.run.conclusion == "success"


@dataclass(frozen=True, slots=True)
class NoBuildNeeded:
    """The branch changed only what the Windows workflow ignores."""


NO_BUILD_NEEDED = NoBuildNeeded()

type Decision = Wait | Result | NoBuildNeeded
type Changed = Callable[[str, str], Sequence[str]]


def ignored_patterns(workflow: str) -> list[str]:
    """The ``paths-ignore`` globs of the Windows workflow, its single source."""
    block = re.search(r"^ *paths-ignore:\n((?: *#.*\n| *- .*\n)+)", workflow, re.MULTILINE)
    if block is None:
        return []
    return re.findall(r'^ *- "?([^"\n]+?)"?\s*$', block.group(1), re.MULTILINE)


def ignorable(path: str, patterns: Sequence[str]) -> bool:
    """Whether GitHub's path filter ignores this file (``**`` any depth, ``*`` within a name)."""
    for pattern in patterns:
        regex = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        if re.fullmatch(regex, path):
            return True
    return False


def decide(  # noqa: PLR0913 - the commit, its history, the runs and how to compare
    commit: str,
    history: Sequence[str],
    runs: Mapping[str, Sequence[Run]],
    *,
    changed: Changed,
    base: str | None,
    patterns: Sequence[str],
    prefer: str | None = None,
) -> Decision:
    """What the check does now. ``history``: the commit, then its ancestors, newest first."""
    for candidate in history:
        if candidate not in runs:
            continue
        if candidate != commit and not all(
            ignorable(path, patterns) for path in changed(candidate, commit)
        ):
            return Wait(None)  # the commit changed what is built: its own run must come
        run = _chosen(runs[candidate], prefer)
        return Result(run) if run.status == "completed" else Wait(run)
    if base is not None and all(ignorable(path, patterns) for path in changed(base, commit)):
        return NO_BUILD_NEEDED
    return Wait(None)


def _chosen(runs: Sequence[Run], prefer: str | None) -> Run:
    preferred = [run for run in runs if run.branch == prefer] or list(runs)
    return max(preferred, key=lambda run: run.created)


def runs_by_commit(payload: Mapping[str, Any]) -> dict[str, list[Run]]:
    grouped: dict[str, list[Run]] = {}
    for item in payload.get("workflow_runs", []):
        created = datetime.fromisoformat(str(item["created_at"]).replace("Z", "+00:00"))
        run = Run(
            str(item["head_sha"]),
            str(item["status"]),
            item.get("conclusion"),
            str(item["html_url"]),
            str(item.get("head_branch") or ""),
            created.timestamp(),
        )
        grouped.setdefault(run.sha, []).append(run)
    return grouped


def fetch_runs(token: str | None) -> dict[str, list[Run]]:
    url = (
        f"https://api.github.com/repos/{MIRROR}/actions/workflows/{WORKFLOW.name}/runs?per_page=100"
    )
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return runs_by_commit(json.load(response))


def latest_runs(
    token: str | None, fetch: Callable[[str | None], dict[str, list[Run]]] = fetch_runs
) -> dict[str, list[Run]] | None:
    """The runs, or ``None`` when GitHub does not answer this time."""
    try:
        return fetch(token)
    except (urllib.error.URLError, TimeoutError) as error:
        print(f"GitHub did not answer ({error}): asking again", file=sys.stderr)
        return None


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def _merge_base(commit: str, branch: str) -> str | None:
    try:
        base = _git("merge-base", commit, branch).strip()
    except subprocess.CalledProcessError:
        return None
    # A commit of the branch itself is no branch of its own: its runs decide
    return None if base == commit else base


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("commit")
    parser.add_argument("--ref", help="the tag being built, whose own run is preferred")
    parser.add_argument("--base", default="origin/main", help="the branch merged into")
    parser.add_argument("--timeout", type=int, default=20 * 60)
    args = parser.parse_args(argv)
    commit = _git("rev-parse", args.commit).strip()
    history = _git("rev-list", f"--max-count={ANCESTORS}", commit).split()
    base = _merge_base(commit, args.base)
    patterns = ignored_patterns(WORKFLOW.read_text(encoding="utf-8"))

    def changed(a: str, b: str) -> list[str]:
        return _git("diff", "--name-only", a, b).split()

    token = os.environ.get("GH_ACTIONS_READ_TOKEN") or None
    deadline = time.monotonic() + args.timeout
    while True:
        runs = latest_runs(token)
        if runs is None:
            if time.monotonic() > deadline:
                print(f"No Windows build result for {commit} in time", file=sys.stderr)
                return 1
            time.sleep(POLL_SECONDS)
            continue
        decision = decide(
            commit,
            history,
            runs,
            changed=changed,
            base=base,
            patterns=patterns,
            prefer=args.ref,
        )
        match decision:
            case Result(run=run) as result:
                print(f"Windows build {run.conclusion}: {run.url}")
                return 0 if result.passed else 1
            case NoBuildNeeded():
                print("Only files the Windows build ignores changed: no build needed")
                return 0
            case Wait(run=run):
                if time.monotonic() > deadline:
                    print(f"No Windows build result for {commit} in time", file=sys.stderr)
                    return 1
                print(f"Waiting for {run.url}" if run else f"Waiting for a run of {commit}")
                time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
