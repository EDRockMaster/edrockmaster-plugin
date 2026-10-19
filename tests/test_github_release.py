import hashlib
import io
import json
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

import pytest

from tests.scripts import load_script

release = load_script("github_release")

DRAFT = {
    "id": 7,
    "tag_name": "v0.7.0",
    "url": "https://api.github.com/repos/r/releases/7",
    "assets": [
        {"id": 11, "name": "EDRockMaster.Companion-stable-Setup.exe"},
        {"id": 12, "name": "releases.stable.json"},
    ],
}


class FakeGitHub:
    """Answers each request with the next item: a JSON body, bytes, or an HTTP error."""

    def __init__(self, *answers: object) -> None:
        self.answers = list(answers)
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> io.BytesIO:
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, urllib.error.HTTPError):
            raise answer
        if isinstance(answer, bytes):
            return io.BytesIO(answer)
        return io.BytesIO(json.dumps(answer).encode())


def refusal(code: int, message: str, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    body = io.BytesIO(json.dumps({"message": message}).encode())
    return urllib.error.HTTPError("https://api.github.com", code, "refused", headers, body)


def redirection(location: str) -> urllib.error.HTTPError:
    headers = Message()
    headers["Location"] = location
    return urllib.error.HTTPError("https://api.github.com", 302, "Found", headers, io.BytesIO())


@pytest.fixture
def waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    slept: list[float] = []
    monkeypatch.setattr(release, "sleep", slept.append)
    monkeypatch.setenv("GH_RELEASE_TOKEN", "token")
    return slept


def github(monkeypatch: pytest.MonkeyPatch, *answers: object) -> FakeGitHub:
    fake = FakeGitHub(*answers)
    monkeypatch.setattr(release, "open_without_redirect", fake)
    return fake


@pytest.fixture
def notes(tmp_path: Path) -> str:
    path = tmp_path / "notes.md"
    path.write_text("The notes", encoding="utf-8")
    return str(path)


@pytest.mark.parametrize(
    "arguments",
    [[], ["fetch", "v0.7.0"], ["publish", "v0.7.0", "notes.md"], ["publish", "v0.7.0", "n", "-x"]],
)
def test_usage(arguments: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    assert release.main(arguments) == 2
    assert "Usage" in capsys.readouterr().err


def test_a_token_is_needed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GH_RELEASE_TOKEN", raising=False)
    assert release.main(["fetch", "v0.7.0", "dist"]) == 2
    assert "GH_RELEASE_TOKEN" in capsys.readouterr().err


def test_the_draft_s_files_are_fetched_with_their_checksums(
    monkeypatch: pytest.MonkeyPatch, waits: list[float], tmp_path: Path
) -> None:
    signed = "https://objects.githubusercontent.com/signed?x=1"
    fake = github(
        monkeypatch,
        [{"id": 6, "tag_name": "v0.6.0", "assets": []}, DRAFT],
        redirection(signed),
        b"MZ setup",
        b'{"Assets": []}',
        {"name": "SHA256SUMS", "size": 140},
    )
    assert release.main(["fetch", "v0.7.0", str(tmp_path / "files")]) == 0
    files = tmp_path / "files"
    assert (files / "EDRockMaster.Companion-stable-Setup.exe").read_bytes() == b"MZ setup"
    setup_sum = hashlib.sha256(b"MZ setup").hexdigest()
    assert f"{setup_sum}  EDRockMaster.Companion-stable-Setup.exe\n" in (
        files / "SHA256SUMS"
    ).read_text(encoding="utf-8")
    listing, asset, followed, feed, uploaded = fake.requests
    assert "per_page=100" in listing.full_url
    assert asset.get_header("Accept") == "application/octet-stream"
    # The signed address gets no token
    assert followed.full_url == signed
    assert followed.get_header("Authorization") is None
    assert feed.get_header("Authorization") == "Bearer token"
    assert uploaded.full_url.endswith("/releases/7/assets?name=SHA256SUMS")
    assert waits == []


def test_no_draft_means_the_windows_build_made_none(
    monkeypatch: pytest.MonkeyPatch,
    waits: list[float],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    github(monkeypatch, [{"id": 6, "tag_name": "v0.6.0", "assets": []}])
    assert release.main(["fetch", "v0.7.0", str(tmp_path)]) == 1
    assert "no release of v0.7.0" in capsys.readouterr().err


def test_a_draft_without_files_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    waits: list[float],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    github(monkeypatch, [{**DRAFT, "assets": []}])
    assert release.main(["fetch", "v0.7.0", str(tmp_path)]) == 1
    assert "carries no file" in capsys.readouterr().err


@pytest.mark.parametrize(("kind", "prerelease"), [("--prerelease", True), ("--release", False)])
@pytest.mark.usefixtures("waits")
def test_the_draft_is_published_with_its_notes(
    monkeypatch: pytest.MonkeyPatch,
    notes: str,
    kind: str,
    prerelease: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = github(monkeypatch, [DRAFT], {"html_url": "https://github.com/r/v0.7.0"})
    assert release.main(["publish", "v0.7.0", notes, kind]) == 0
    patch = fake.requests[1]
    assert patch.get_method() == "PATCH"
    assert patch.full_url.endswith("/releases/7")
    assert isinstance(patch.data, bytes)
    assert json.loads(patch.data) == {
        "name": "EDRockMaster v0.7.0",
        "body": "The notes",
        "prerelease": prerelease,
        "draft": False,
    }
    assert "https://github.com/r/v0.7.0" in capsys.readouterr().out


def test_a_passing_refusal_is_tried_again(
    monkeypatch: pytest.MonkeyPatch,
    waits: list[float],
    notes: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    github(
        monkeypatch,
        refusal(403, "You have exceeded a secondary rate limit", retry_after="7"),
        refusal(502, "Bad gateway"),
        [DRAFT],
        {"html_url": "https://github.com/r/v0.7.0"},
    )
    assert release.main(["publish", "v0.7.0", notes, "--release"]) == 0
    assert waits == [7.0, 40.0]
    assert "secondary rate limit" in capsys.readouterr().out


def test_a_lasting_refusal_says_github_s_message(
    monkeypatch: pytest.MonkeyPatch,
    waits: list[float],
    notes: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    denied = "Resource not accessible by personal access token"
    github(monkeypatch, *(refusal(403, denied) for _ in range(3)))
    assert release.main(["publish", "v0.7.0", notes, "--release"]) == 1
    assert waits == [20.0, 40.0]
    assert f"HTTP 403: {denied}" in capsys.readouterr().err


def test_a_refusal_that_will_not_pass_is_not_tried_again(
    monkeypatch: pytest.MonkeyPatch,
    waits: list[float],
    notes: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    github(monkeypatch, refusal(401, "Bad credentials"))
    assert release.main(["publish", "v0.7.0", notes, "--release"]) == 1
    assert waits == []
    assert "HTTP 401: Bad credentials" in capsys.readouterr().err


def test_a_message_that_is_not_json_is_shown_as_text() -> None:
    error = urllib.error.HTTPError(
        "https://api.github.com", 502, "Bad Gateway", Message(), io.BytesIO(b"<html>oops</html>")
    )
    assert release._message(error) == "<html>oops</html>"
