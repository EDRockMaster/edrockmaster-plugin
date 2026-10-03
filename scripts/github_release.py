"""Publish a release of the plugin on GitHub, where players download it.

Talks to api.github.com explicitly: under Gitea Actions, GITHUB_API_URL points
at Gitea, and JavaScript actions cannot be made to ignore it. Idempotent: an
existing release of the tag is reused, an asset already attached is replaced.

Usage: GH_RELEASE_TOKEN=... python3 scripts/github_release.py \
           <tag> <target commit> <notes file> <asset>...
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPOSITORY = "EDRockMaster/edrockmaster-plugin"
API = f"https://api.github.com/repos/{REPOSITORY}"
UPLOADS = f"https://uploads.github.com/repos/{REPOSITORY}"


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
    with urllib.request.urlopen(
        urllib.request.Request(url, data=body, headers=headers, method=method), timeout=60
    ) as response:
        payload = response.read()
    return json.loads(payload) if payload else None


def release_for(tag: str, target: str, notes: str, token: str) -> dict[str, Any]:
    try:
        existing: dict[str, Any] = request("GET", f"{API}/releases/tags/{tag}", token)
        print(f"Release {tag} already exists, reusing it")
        return existing
    except urllib.error.HTTPError as error:
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
    if len(arguments) < 4:
        print(__doc__, file=sys.stderr)
        return 2
    token = os.environ.get("GH_RELEASE_TOKEN", "")
    if not token:
        print("GH_RELEASE_TOKEN is not set", file=sys.stderr)
        return 2
    tag, target, notes_file, *assets = arguments
    release = release_for(tag, target, Path(notes_file).read_text(encoding="utf-8"), token)
    for asset in assets:
        upload(release, Path(asset), token)
    print(release["html_url"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
