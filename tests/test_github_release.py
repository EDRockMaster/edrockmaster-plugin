import io
import json
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

import pytest

from tests.scripts import load_script

release = load_script("github_release")


def test_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert release.main(["v0.4.0", "abc1234"]) == 2
    assert "Usage" in capsys.readouterr().err


def test_a_token_is_needed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GH_RELEASE_TOKEN", raising=False)
    # Notes only, no file: what a production of the desktop application publishes (ADR 0024)
    assert release.main(["v0.4.0", "abc1234", "notes.md"]) == 2
    assert "GH_RELEASE_TOKEN" in capsys.readouterr().err


class FakeGitHub:
    """Answers each request with the next item: a JSON body, or an HTTP error to raise."""

    def __init__(self, *answers: object) -> None:
        self.answers = list(answers)
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> io.BytesIO:
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, urllib.error.HTTPError):
            raise answer
        return io.BytesIO(json.dumps(answer).encode())


def refusal(code: int, message: str, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    body = io.BytesIO(json.dumps({"message": message}).encode())
    return urllib.error.HTTPError("https://api.github.com", code, "refused", headers, body)


@pytest.fixture
def waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    slept: list[float] = []
    monkeypatch.setattr(release, "sleep", slept.append)
    monkeypatch.setenv("GH_RELEASE_TOKEN", "token")
    return slept


@pytest.fixture
def notes(tmp_path: Path) -> str:
    path = tmp_path / "notes.md"
    path.write_text("The notes", encoding="utf-8")
    return str(path)


def test_a_new_release_is_created(
    monkeypatch: pytest.MonkeyPatch,
    waits: list[float],
    notes: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    github = FakeGitHub(refusal(404, "Not Found"), {"html_url": "https://github.com/r/v0.6.0"})
    monkeypatch.setattr(release.urllib.request, "urlopen", github)
    assert release.main(["v0.6.0", "abc1234", notes]) == 0
    get, post = github.requests
    assert (get.get_method(), post.get_method()) == ("GET", "POST")
    assert isinstance(post.data, bytes)
    assert json.loads(post.data)["body"] == "The notes"
    assert waits == []
    assert "https://github.com/r/v0.6.0" in capsys.readouterr().out


def test_a_passing_refusal_is_tried_again(
    monkeypatch: pytest.MonkeyPatch,
    waits: list[float],
    notes: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    github = FakeGitHub(
        refusal(404, "Not Found"),
        refusal(403, "You have exceeded a secondary rate limit", retry_after="7"),
        refusal(502, "Bad gateway"),
        {"html_url": "https://github.com/r/v0.6.0"},
    )
    monkeypatch.setattr(release.urllib.request, "urlopen", github)
    assert release.main(["v0.6.0", "abc1234", notes]) == 0
    assert waits == [7.0, 40.0]
    assert "secondary rate limit" in capsys.readouterr().out


def test_a_lasting_refusal_says_github_s_message(
    monkeypatch: pytest.MonkeyPatch,
    waits: list[float],
    notes: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    denied = "Resource not accessible by personal access token"
    github = FakeGitHub(refusal(404, "Not Found"), *(refusal(403, denied) for _ in range(3)))
    monkeypatch.setattr(release.urllib.request, "urlopen", github)
    assert release.main(["v0.6.0", "abc1234", notes]) == 1
    assert waits == [20.0, 40.0]
    assert f"HTTP 403: {denied}" in capsys.readouterr().err


def test_a_refusal_that_will_not_pass_is_not_tried_again(
    monkeypatch: pytest.MonkeyPatch,
    waits: list[float],
    notes: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    github = FakeGitHub(refusal(401, "Bad credentials"))
    monkeypatch.setattr(release.urllib.request, "urlopen", github)
    assert release.main(["v0.6.0", "abc1234", notes]) == 1
    assert waits == []
    assert "HTTP 401: Bad credentials" in capsys.readouterr().err


def test_a_message_that_is_not_json_is_shown_as_text() -> None:
    error = urllib.error.HTTPError(
        "https://api.github.com", 502, "Bad Gateway", Message(), io.BytesIO(b"<html>oops</html>")
    )
    assert release._message(error) == "<html>oops</html>"
