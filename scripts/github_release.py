"""Publish a release on GitHub: its notes, and the files given, if any.

A production release carries the release notes and the sources only (ADR 0022,
ADR 0024): players get the application from the Microsoft Store, and the
release's publication triggers the Discord announcement (a webhook of the
repository). Talks to api.github.com explicitly: under Gitea Actions, GITHUB_API_URL points
at Gitea, and JavaScript actions cannot be made to ignore it. Idempotent: an
existing release of the tag is reused, an asset already attached is replaced.

GitHub sometimes refuses a request for a moment (a 403 or 429 of its secondary rate
limit, or a 5xx): it is tried again, up to three times, after its ``Retry-After`` or
20 then 40 seconds. A refusal says GitHub's own message, so that the CI log tells a
passing limit from a token without the right to write.

Usage: GH_RELEASE_TOKEN=... python3 scripts/github_release.py \
           <tag> <target commit> <notes file> [<asset>...]
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPOSITORY = "EDRockMaster/edrockmaster-plugin"
API = f"https://api.github.com/repos/{REPOSITORY}"
UPLOADS = f"https://uploads.github.com/repos/{REPOSITORY}"
ATTEMPTS = 3
FIRST_WAIT = 20.0
_PASSING = frozenset({403, 429, 500, 502, 503, 504})
sleep = time.sleep


class GitHubError(Exception):
    """GitHub refused a request; ``code`` is its HTTP status, the message GitHub's own."""

    def __init__(self, method: str, url: str, code: int, message: str) -> None:
        super().__init__(f"{method} {url}: HTTP {code}: {message}")
        self.code = code


def _message(error: urllib.error.HTTPError) -> str:
    try:
        body = error.read().decode("utf-8", errors="replace")
    except OSError:
        return error.reason or ""
    try:
        return str(json.loads(body)["message"])
    except (ValueError, KeyError, TypeError):
        return body.strip()[:300] or str(error.reason)


def _wait(error: urllib.error.HTTPError, attempt: int) -> float:
    try:
        return float(error.headers.get("Retry-After", ""))
    except ValueError:
        return FIRST_WAIT * attempt


def request(
    method: str, url: str, token: str, body: bytes | None = None, content_type: str = ""
) -> Any:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if content_type:
        headers["Content-Type"] = content_type
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, data=body, headers=headers, method=method), timeout=60
            ) as response:
                payload = response.read()
            return json.loads(payload) if payload else None
        except urllib.error.HTTPError as error:
            message = _message(error)
            if error.code not in _PASSING or attempt == ATTEMPTS:
                raise GitHubError(method, url, error.code, message) from error
            wait = _wait(error, attempt)
            print(f"GitHub refused {method} {url} ({error.code}: {message}), again in {wait:.0f} s")
            sleep(wait)
    raise AssertionError("unreachable")  # pragma: no cover - the loop returns or raises


def release_for(tag: str, target: str, notes: str, token: str) -> dict[str, Any]:
    try:
        existing: dict[str, Any] = request("GET", f"{API}/releases/tags/{tag}", token)
        print(f"Release {tag} already exists, reusing it")
        return existing
    except GitHubError as error:
        if error.code != 404:
            raise
    payload = {
        "tag_name": tag,
        "target_commitish": target,
        "name": f"EDRockMaster {tag}",
        "body": notes,
    }
    created: dict[str, Any] = request(
        "POST", f"{API}/releases", token, json.dumps(payload).encode(), "application/json"
    )
    print(f"Release {tag} created")
    return created


def upload(release: dict[str, Any], asset: Path, token: str) -> None:
    for existing in release.get("assets", []):
        if existing["name"] == asset.name:
            request("DELETE", f"{API}/releases/assets/{existing['id']}", token)
    query = urllib.parse.urlencode({"name": asset.name})
    uploaded = request(
        "POST",
        f"{UPLOADS}/releases/{release['id']}/assets?{query}",
        token,
        asset.read_bytes(),
        "application/zip",
    )
    print(f"Uploaded {uploaded['name']} ({uploaded['size']} bytes)")


def main(arguments: list[str]) -> int:
    if len(arguments) < 3:  # tag, commit, notes
        print(__doc__, file=sys.stderr)
        return 2
    token = os.environ.get("GH_RELEASE_TOKEN", "")
    if not token:
        print("GH_RELEASE_TOKEN is not set", file=sys.stderr)
        return 2
    tag, target, notes_file, *assets = arguments
    try:
        release = release_for(tag, target, Path(notes_file).read_text(encoding="utf-8"), token)
        for asset in assets:
            upload(release, Path(asset), token)
    except GitHubError as error:
        print(f"GitHub refused the release: {error}", file=sys.stderr)
        return 1
    print(release["html_url"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
