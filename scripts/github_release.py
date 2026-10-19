"""Finish and publish the GitHub release of a tag (ADR 0053).

The Windows workflow of the GitHub mirror packs a tag with Velopack and leaves its
release as a **draft** carrying the installer, the portable zip, the packages and the
update feeds (``vpk upload github``). The release job of the Gitea CI then:

- ``fetch``: downloads the draft's files into a folder, for the Gitea release, and adds a
  ``SHA256SUMS`` file of them to both;
- ``publish``: gives the draft its notes and name, marks a candidate as a pre-release, and
  publishes it. Publishing a production triggers the Discord announcement (a webhook of the
  repository, which ignores pre-releases); the updates of installed applications read the
  published releases only.

Talks to api.github.com explicitly: under Gitea Actions, GITHUB_API_URL points at Gitea, and
JavaScript actions cannot be made to ignore it. GitHub sometimes refuses a request for a moment
(a 403 or 429 of its secondary rate limit, or a 5xx): it is tried again, up to three times,
after its ``Retry-After`` or 20 then 40 seconds. A refusal says GitHub's own message, so that
the CI log tells a passing limit from a token without the right to write.

Usage: GH_RELEASE_TOKEN=... python3 scripts/github_release.py fetch <tag> <folder>
       GH_RELEASE_TOKEN=... python3 scripts/github_release.py publish <tag> <notes file> \
           (--prerelease | --release)
"""

from __future__ import annotations

import hashlib
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
CHECKSUMS = "SHA256SUMS"
PAGE = 100
PAGES = 10
"""The releases looked through for a tag's draft: the latest thousand."""
_PASSING = frozenset({403, 429, 500, 502, 503, 504})
sleep = time.sleep


class GitHubError(Exception):
    """GitHub refused a request; ``code`` is its HTTP status, the message GitHub's own."""

    def __init__(self, method: str, url: str, code: int, message: str) -> None:
        super().__init__(f"{method} {url}: HTTP {code}: {message}")
        self.code = code


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None  # the redirection is raised as an HTTPError, its Location then followed


open_without_redirect = urllib.request.build_opener(_NoRedirect).open
"""An asset's download answers with a redirection to a signed address, which must not get the
token: it is followed apart."""


class Redirected(Exception):  # noqa: N818 - not an error: where the asset is
    def __init__(self, location: str) -> None:
        super().__init__(location)
        self.location = location


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


def _headers(token: str | None, accept: str, content_type: str) -> dict[str, str]:
    headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _open(  # noqa: PLR0913 - an HTTP request, its token, body and kind
    method: str,
    url: str,
    token: str | None,
    body: bytes | None = None,
    content_type: str = "",
    *,
    accept: str = "application/vnd.github+json",
) -> bytes:
    """The answer's body; a redirection raises ``Redirected``."""
    request = urllib.request.Request(
        url, data=body, headers=_headers(token, accept, content_type), method=method
    )
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with open_without_redirect(request, timeout=120) as response:
                return bytes(response.read())
        except urllib.error.HTTPError as error:
            if error.code in (301, 302, 307):
                raise Redirected(error.headers["Location"]) from error
            message = _message(error)
            if error.code not in _PASSING or attempt == ATTEMPTS:
                raise GitHubError(method, url, error.code, message) from error
            wait = _wait(error, attempt)
            print(f"GitHub refused {method} {url} ({error.code}: {message}), again in {wait:.0f} s")
            sleep(wait)
    raise AssertionError("unreachable")  # pragma: no cover - the loop returns or raises


def request(
    method: str, url: str, token: str, body: bytes | None = None, content_type: str = ""
) -> Any:
    payload = _open(method, url, token, body, content_type)
    return json.loads(payload) if payload else None


def draft_of(tag: str, token: str) -> dict[str, Any]:
    """The release of the tag, drafts included (the tags endpoint does not show drafts)."""
    for page in range(1, PAGES + 1):
        releases: list[dict[str, Any]] = request(
            "GET", f"{API}/releases?per_page={PAGE}&page={page}", token
        )
        for found in releases:
            if found["tag_name"] == tag:
                return found
        if len(releases) < PAGE:
            break
    raise GitHubError(
        "GET", f"{API}/releases", 404, f"no release of {tag}: the Windows build left none"
    )


def download(asset: dict[str, Any], folder: Path, token: str) -> Path:
    url = f"{API}/releases/assets/{asset['id']}"
    try:
        content = _open("GET", url, token, accept="application/octet-stream")
    except Redirected as redirected:
        content = _open("GET", redirected.location, None, accept="application/octet-stream")
    target = folder / Path(str(asset["name"])).name  # a bare name, never a path elsewhere
    target.write_bytes(content)
    print(f"Downloaded {target.name} ({len(content)} bytes)")
    return target


def checksums(files: list[Path]) -> str:
    """``sha256sum`` lines of the files, by name."""
    return "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sorted(files, key=lambda path: path.name)
    )


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
        "application/octet-stream",
    )
    print(f"Uploaded {uploaded['name']} ({uploaded['size']} bytes)")


def fetch(tag: str, folder: Path, token: str) -> None:
    release = draft_of(tag, token)
    folder.mkdir(parents=True, exist_ok=True)
    files = [
        download(asset, folder, token)
        for asset in release.get("assets", [])
        if asset["name"] != CHECKSUMS
    ]
    if not files:
        raise GitHubError("GET", release["url"], 404, f"the release of {tag} carries no file")
    sums = folder / CHECKSUMS
    sums.write_text(checksums(files), encoding="utf-8")
    upload(release, sums, token)


def publish(tag: str, notes: str, prerelease: bool, token: str) -> str:
    release = draft_of(tag, token)
    payload = {
        "name": f"EDRockMaster {tag}",
        "body": notes,
        "prerelease": prerelease,
        "draft": False,
    }
    published: dict[str, Any] = request(
        "PATCH",
        f"{API}/releases/{release['id']}",
        token,
        json.dumps(payload).encode(),
        "application/json",
    )
    return str(published["html_url"])


def _command(arguments: list[str]) -> tuple[str, str, str, bool] | None:
    """``(command, tag, path, prerelease)``, or ``None`` for a wrong usage."""
    match arguments:
        case ["fetch", tag, folder]:
            return "fetch", tag, folder, False
        case ["publish", tag, notes, ("--prerelease" | "--release") as kind]:
            return "publish", tag, notes, kind == "--prerelease"
        case _:
            return None


def main(arguments: list[str]) -> int:
    command = _command(arguments)
    if command is None:
        print(__doc__, file=sys.stderr)
        return 2
    token = os.environ.get("GH_RELEASE_TOKEN", "")
    if not token:
        print("GH_RELEASE_TOKEN is not set", file=sys.stderr)
        return 2
    name, tag, path, prerelease = command
    try:
        if name == "fetch":
            fetch(tag, Path(path), token)
        else:
            print(publish(tag, Path(path).read_text(encoding="utf-8"), prerelease, token))
    except GitHubError as error:
        print(f"GitHub refused the release: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
